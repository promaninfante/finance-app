import hmac
import json
import logging

from shared.ssm import load_secrets
from shared.supabase_client import SupabaseClient, SupabaseError
from .classify import classify_transactions
from .drive import DriveFileNotFoundError, DrivePermissionError, fetch_drive_file
from .extract import build_tx_row, extract_transactions

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict, context) -> dict:
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    secrets = load_secrets()

    # --- C3: secret validation ---
    provided = headers.get("x-ingest-secret", "")
    if not hmac.compare_digest(provided, secrets["ingest_shared_secret"]):
        return _response(401, {"error": "Unauthorized"})

    # --- parse body ---
    try:
        body = json.loads(event.get("body") or "{}")
        user_id       = body["user_id"]
        account_id    = body["account_id"]
        drive_file_id = body["drive_file_id"]
        filename      = body["filename"]
    except (KeyError, json.JSONDecodeError) as exc:
        return _response(400, {"error": f"Bad request: {exc}"})

    db = SupabaseClient(secrets["supabase_url"], secrets["supabase_service_key"])
    statement_id = None

    try:
        # --- C5: insert statement row (dedup via unique constraint) ---
        try:
            row = db.insert("statements", {
                "user_id":       user_id,
                "account_id":    account_id,
                "filename":      filename,
                "drive_file_id": drive_file_id,
                "status":        "pending",
            })
            statement_id = row["id"]
            logger.info("Created statement %s for file %s", statement_id, drive_file_id)
        except SupabaseError as exc:
            if exc.status_code == 409:
                logger.info("Duplicate drive_file_id %s — skipping", drive_file_id)
                return _response(200, {"status": "duplicate"})
            raise

        # mark processing
        db.update("statements", {"id": statement_id}, {"status": "processing"})

        # --- C4: download PDF ---
        pdf_bytes = fetch_drive_file(drive_file_id, secrets["google_service_account_json"])
        logger.info("Downloaded %d bytes for statement %s", len(pdf_bytes), statement_id)

        # --- D+E: extract, classify, and insert transactions with dedup ---
        raw_transactions = extract_transactions(pdf_bytes, secrets)
        classified_txs = classify_transactions(raw_transactions, user_id, db, secrets)
        inserted = 0
        for raw_tx in classified_txs:
            row = build_tx_row(raw_tx, user_id, statement_id, account_id)
            try:
                db.insert("transactions", row)
                inserted += 1
            except SupabaseError as exc:
                if exc.status_code == 409:
                    logger.debug("Duplicate tx_hash %s — skipping", row["tx_hash"])
                else:
                    raise
        logger.info("Inserted %d/%d transactions for statement %s", inserted, len(classified_txs), statement_id)

        db.update("statements", {"id": statement_id}, {
            "status":       "done",
            "processed_at": "now()",
        })
        logger.info("Statement %s done", statement_id)
        return _response(200, {"status": "ok", "statement_id": statement_id})

    except (DriveFileNotFoundError, DrivePermissionError) as exc:
        logger.error("Drive error for %s: %s", drive_file_id, exc)
        _mark_error(db, statement_id, str(exc))
        return _response(200, {"status": "error", "detail": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error processing %s", drive_file_id)
        _mark_error(db, statement_id, str(exc))
        return _response(200, {"status": "error", "detail": str(exc)})


def _mark_error(db: SupabaseClient, statement_id: str | None, message: str) -> None:
    if statement_id:
        try:
            db.update("statements", {"id": statement_id}, {
                "status":        "error",
                "error_message": message[:500],
            })
        except Exception:
            pass  # best-effort; don't mask the original error


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
