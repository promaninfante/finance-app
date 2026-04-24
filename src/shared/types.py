from typing import Literal, TypedDict


ClassificationSource = Literal["llm", "rule", "manual"]
StatementStatus = Literal["pending", "processing", "done", "error"]


class Secrets(TypedDict):
    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: str
    google_service_account_json: str
    ingest_shared_secret: str
    telegram_bot_token: str
    telegram_webhook_secret: str


class StatementInsert(TypedDict):
    user_id: str
    account_id: str
    filename: str
    drive_file_id: str
    status: StatementStatus


class TransactionInsert(TypedDict, total=False):
    user_id: str
    statement_id: str
    account_id: str
    date: str            # ISO 8601: "2024-03-15"
    description: str
    amount: float        # negative = expense, positive = income
    currency: str        # ISO 4217: "EUR"
    classification_source: ClassificationSource
    is_reviewed: bool
    notes: str
