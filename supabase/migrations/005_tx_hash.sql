-- D2: Add tx_hash for transaction-level deduplication across re-drops of the same PDF.
-- Hash is sha256("{account_id}|{date}|{amount:.2f}|{description}"), computed by the Lambda.
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS tx_hash TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uix_transactions_user_tx_hash
    ON transactions(user_id, tx_hash)
    WHERE tx_hash IS NOT NULL;
