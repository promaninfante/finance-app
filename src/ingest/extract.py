import hashlib
import io
import json
import logging

import boto3
from pypdf import PdfReader

logger = logging.getLogger(__name__)

# eu. prefix = cross-region inference profile (routes across eu-west-1/eu-central-1/eu-west-3).
# To swap models, change this one line — the Converse API call below is model-agnostic.
_MODEL_ID = "eu.amazon.nova-micro-v1:0"

_SYSTEM = (
    "You are a precise financial data extractor. "
    "Extract ALL transactions from the bank statement text below. "
    "Return a JSON array only — no markdown fences, no explanation. "
    "Each element must have exactly these fields:\n"
    '  "date"        : transaction date, ISO 8601 (YYYY-MM-DD)\n'
    '  "description" : merchant or payee exactly as printed\n'
    '  "amount"      : float — negative for debits/charges, positive for credits\n'
    '  "currency"    : 3-letter ISO code (default EUR if not shown)\n'
    "Exclude opening/closing balances and period summaries. "
    "Include every individual line item."
)


def extract_transactions(pdf_bytes: bytes, secrets: dict) -> list[dict]:
    """
    Extract transactions from PDF bytes via pypdf text extraction + Bedrock.
    Returns list of dicts: {date, description, amount, currency}.
    Raises ValueError if the PDF has no extractable text or LLM returns bad JSON.
    """
    text = _extract_text(pdf_bytes)
    if not text.strip():
        raise ValueError(
            "pypdf extracted no text — this may be a scanned/image PDF, "
            "which is not supported in Milestone D."
        )
    raw = _call_bedrock(text)
    return _validate(raw)


def build_tx_row(
    raw: dict,
    user_id: str,
    statement_id: str,
    account_id: str,
) -> dict:
    """Convert a raw extracted (and classified) transaction dict into a DB-ready row."""
    date        = raw["date"]
    description = raw["description"]
    amount      = round(float(raw["amount"]), 2)
    currency    = raw.get("currency", "EUR").upper()
    category_id = raw.get("category_id")
    source      = raw.get("classification_source", "llm")

    tx_hash = hashlib.sha256(
        f"{account_id}|{date}|{amount:.2f}|{description}".encode()
    ).hexdigest()

    row = {
        "user_id":               user_id,
        "statement_id":          statement_id,
        "account_id":            account_id,
        "date":                  date,
        "description":           description,
        "amount":                amount,
        "currency":              currency,
        "classification_source": source,
        "is_reviewed":           source == "rule",
        "tx_hash":               tx_hash,
    }
    if category_id is not None:
        row["category_id"]          = category_id
        row["original_category_id"] = category_id
    return row


def _extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _call_bedrock(text: str) -> str:
    client = boto3.client("bedrock-runtime", region_name="eu-west-1")
    response = client.converse(
        modelId=_MODEL_ID,
        system=[{"text": _SYSTEM}],
        messages=[{
            "role": "user",
            "content": [{"text": f"Statement text:\n\n{text}"}],
        }],
        inferenceConfig={"maxTokens": 4096},
    )
    return response["output"]["message"]["content"][0]["text"]


def _validate(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON: {raw[:300]}") from exc
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data).__name__}: {str(data)[:200]}")
    required = {"date", "description", "amount", "currency"}
    for i, item in enumerate(data):
        missing = required - item.keys()
        if missing:
            raise ValueError(f"Transaction {i} missing fields {missing}: {item}")
    logger.info("Extracted %d transactions from statement", len(data))
    return data
