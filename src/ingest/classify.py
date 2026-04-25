import json
import logging

import boto3

from shared.supabase_client import SupabaseClient, SupabaseError
from .normalize import normalize_merchant

logger = logging.getLogger(__name__)

_MODEL_ID = "eu.amazon.nova-micro-v1:0"
_FALLBACK = "Other"

_CLASSIFY_SYSTEM = (
    "You are a precise transaction categorizer for a personal finance app. "
    "You receive a JSON object with a 'categories' list and a 'transactions' list. "
    "Return a JSON array of category names — one per transaction, same order. "
    "Every name must exactly match one of the provided categories. "
    "Use 'Other' if unsure. No markdown, no explanation — JSON array only."
)


def classify_transactions(
    raw_txs: list[dict],
    user_id: str,
    db: SupabaseClient,
    secrets: dict,
) -> list[dict]:
    """Augment each tx dict with category_id, classification_source, merchant_rule_id.

    Non-fatal: if classification fails entirely, returns input unchanged with source='llm'
    and category_id=None so transactions are still inserted.
    """
    try:
        return _classify(raw_txs, user_id, db, secrets)
    except Exception:
        logger.exception("classify_transactions failed; all transactions left uncategorized")
        for tx in raw_txs:
            tx.setdefault("category_id", None)
            tx.setdefault("classification_source", "llm")
            tx.setdefault("merchant_rule_id", None)
        return raw_txs


def _classify(raw_txs: list[dict], user_id: str, db: SupabaseClient, secrets: dict) -> list[dict]:
    categories = _load_categories(user_id, db)
    if not categories:
        logger.warning("No categories found for user %s — skipping classification", user_id)
        for tx in raw_txs:
            tx.update({"category_id": None, "classification_source": "llm", "merchant_rule_id": None})
        return raw_txs

    rules = _load_rules(user_id, db)
    unmatched_indices = []

    for i, tx in enumerate(raw_txs):
        normalized = normalize_merchant(tx["description"])
        rule = _match_rules(normalized, rules)
        if rule:
            tx["category_id"]           = rule["category_id"]
            tx["classification_source"] = "rule"
            tx["merchant_rule_id"]      = rule["id"]
            _increment_hit(rule["id"], db)
        else:
            tx["category_id"]           = None
            tx["classification_source"] = "llm"
            tx["merchant_rule_id"]      = None
            unmatched_indices.append(i)

    if unmatched_indices:
        descs = [normalize_merchant(raw_txs[i]["description"]) for i in unmatched_indices]
        names = _llm_classify_batch(descs, list(categories.keys()), secrets)
        cat_lower = {k.lower(): v for k, v in categories.items()}
        for j, i in enumerate(unmatched_indices):
            cat_name = names[j]
            cat_id   = cat_lower.get(cat_name.lower())
            raw_txs[i]["category_id"] = cat_id
            if cat_id:
                raw_txs[i]["merchant_rule_id"] = _create_tentative_rule(
                    descs[j], cat_id, user_id, db
                )

    rule_count = sum(1 for t in raw_txs if t.get("classification_source") == "rule")
    logger.info(
        "Classified %d txs: %d by rule, %d by llm",
        len(raw_txs), rule_count, len(raw_txs) - rule_count,
    )
    return raw_txs


def _load_categories(user_id: str, db: SupabaseClient) -> dict[str, str]:
    """Returns {name: id} for system categories (user_id IS NULL) + user's own."""
    rows = db.select_many(
        "categories",
        filters={"or": f"(user_id.is.null,user_id.eq.{user_id})"},
        order="name.asc",
    )
    return {row["name"]: row["id"] for row in rows}


def _load_rules(user_id: str, db: SupabaseClient) -> list[dict]:
    """Returns confirmed rules ordered by priority DESC."""
    return db.select_many(
        "merchant_rules",
        filters={"user_id": f"eq.{user_id}", "user_confirmed": "eq.true"},
        order="priority.desc",
    )


def _match_rules(normalized: str, rules: list[dict]) -> dict | None:
    for rule in rules:
        if rule["pattern"].upper() in normalized:
            return rule
    return None


def _increment_hit(rule_id: str, db: SupabaseClient) -> None:
    try:
        db.rpc("increment_rule_hit", {"p_rule_id": rule_id})
    except Exception:
        logger.debug("hit_count increment failed for rule %s (non-fatal)", rule_id)


def _llm_classify_batch(
    descriptions: list[str],
    category_names: list[str],
    secrets: dict,
) -> list[str]:
    if not descriptions:
        return []
    payload = {
        "categories": category_names,
        "transactions": [{"index": i, "description": d} for i, d in enumerate(descriptions)],
    }
    client = boto3.client("bedrock-runtime", region_name="eu-west-1")
    response = client.converse(
        modelId=_MODEL_ID,
        system=[{"text": _CLASSIFY_SYSTEM}],
        messages=[{"role": "user", "content": [{"text": json.dumps(payload)}]}],
        inferenceConfig={"maxTokens": 1024},
    )
    raw = response["output"]["message"]["content"][0]["text"]
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list) or len(parsed) != len(descriptions):
            raise ValueError(f"expected {len(descriptions)} items, got {len(parsed) if isinstance(parsed, list) else type(parsed).__name__}")
        valid = {n.lower() for n in category_names}
        return [item if isinstance(item, str) and item.lower() in valid else _FALLBACK for item in parsed]
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("LLM batch classify returned bad JSON (%s) — falling back to '%s'", exc, _FALLBACK)
        return [_FALLBACK] * len(descriptions)


def _create_tentative_rule(
    pattern: str,
    category_id: str,
    user_id: str,
    db: SupabaseClient,
) -> str | None:
    if not pattern:
        return None
    try:
        row = db.insert("merchant_rules", {
            "user_id":        user_id,
            "pattern":        pattern,
            "category_id":    category_id,
            "priority":       0,
            "user_confirmed": False,
            "hit_count":      1,
        })
        return row.get("id")
    except SupabaseError as exc:
        if exc.status_code != 409:
            logger.warning("Could not create tentative rule for '%s': %s", pattern, exc)
        return None
