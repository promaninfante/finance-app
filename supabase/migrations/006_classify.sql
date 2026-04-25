-- E: extend merchant_rules for learning loop
-- hit_count    — incremented each time this rule matches a transaction
-- user_confirmed — FALSE = tentative (LLM-generated); TRUE = user has verified in Review UI

ALTER TABLE merchant_rules
    ADD COLUMN IF NOT EXISTS hit_count      INT     NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS user_confirmed BOOLEAN NOT NULL DEFAULT FALSE;

-- Prevent duplicate tentative rules for the same pattern per user
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uix_merchant_rules_user_pattern'
    ) THEN
        ALTER TABLE merchant_rules
            ADD CONSTRAINT uix_merchant_rules_user_pattern UNIQUE (user_id, pattern);
    END IF;
END $$;

-- Partial index: fast load of confirmed rules only (hot path in classification)
CREATE INDEX IF NOT EXISTS idx_merchant_rules_confirmed
    ON merchant_rules(user_id, priority DESC)
    WHERE user_confirmed = TRUE;

-- Atomic server-side hit_count increment (avoids read-modify-write in Lambda)
CREATE OR REPLACE FUNCTION increment_rule_hit(p_rule_id UUID)
RETURNS VOID LANGUAGE sql SECURITY DEFINER AS $$
    UPDATE merchant_rules SET hit_count = hit_count + 1 WHERE id = p_rule_id;
$$;
