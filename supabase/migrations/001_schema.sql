-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- USER PROFILES
-- telegram_chat_id bridges the Telegram bot to a Supabase user.
-- ============================================================
CREATE TABLE user_profiles (
    id                 UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name       TEXT,
    telegram_chat_id   BIGINT      UNIQUE,
    preferred_currency CHAR(3)     NOT NULL DEFAULT 'EUR',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- CATEGORIES
-- user_id IS NULL → system default visible to all users
-- user_id = uuid  → user-created custom category
-- ============================================================
CREATE TABLE categories (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID        REFERENCES auth.users(id) ON DELETE CASCADE,
    name       TEXT        NOT NULL,
    color      TEXT        NOT NULL DEFAULT '#6B7280',
    icon       TEXT        NOT NULL DEFAULT 'tag',
    is_system  BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, name)
);

-- ============================================================
-- ACCOUNTS
-- ============================================================
CREATE TABLE accounts (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name       TEXT        NOT NULL,
    bank_name  TEXT        NOT NULL,
    currency   CHAR(3)     NOT NULL DEFAULT 'EUR',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- STATEMENTS  (one row per uploaded PDF)
-- account_id NOT NULL — user selects account on upload.
-- drive_file_id UNIQUE per user — statement-level deduplication.
-- ============================================================
CREATE TABLE statements (
    id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    account_id    UUID        NOT NULL REFERENCES accounts(id),
    filename      TEXT        NOT NULL,
    drive_file_id TEXT,
    status        TEXT        NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending','processing','done','error')),
    error_message TEXT,
    uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at  TIMESTAMPTZ,
    UNIQUE (user_id, drive_file_id)
);

-- ============================================================
-- MERCHANTS  (global — writable via service role only)
-- ============================================================
CREATE TABLE merchants (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT        NOT NULL UNIQUE,
    normalized_name TEXT        NOT NULL,
    category_id     UUID        REFERENCES categories(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- MERCHANT RULES  (user text-pattern → category)
-- ============================================================
CREATE TABLE merchant_rules (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    pattern     TEXT        NOT NULL,
    category_id UUID        NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    priority    INT         NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- TRANSACTIONS
-- Expenses are negative amounts; income is positive.
-- classification_source has no default — Lambda must always set it explicitly.
-- original_category_id stores the llm/rule suggestion before any manual override.
-- updated_at is maintained by a trigger (see 002_rls.sql).
-- ============================================================
CREATE TABLE transactions (
    id                   UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id              UUID          NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    statement_id         UUID          REFERENCES statements(id) ON DELETE SET NULL,
    account_id           UUID          REFERENCES accounts(id) ON DELETE SET NULL,
    date                 DATE          NOT NULL,
    description          TEXT          NOT NULL,
    amount               NUMERIC(12,2) NOT NULL CHECK (amount != 0),
    currency             CHAR(3)       NOT NULL DEFAULT 'EUR',
    merchant_id          UUID          REFERENCES merchants(id) ON DELETE SET NULL,
    category_id          UUID          REFERENCES categories(id) ON DELETE SET NULL,
    original_category_id UUID          REFERENCES categories(id) ON DELETE SET NULL,
    classification_source TEXT         NOT NULL
                                       CHECK (classification_source IN ('llm','rule','manual')),
    is_reviewed          BOOLEAN       NOT NULL DEFAULT FALSE,
    notes                TEXT,
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ============================================================
-- BUDGETS
-- Auto-renews every period while is_active = TRUE.
-- start_date records when the budget first became active.
-- Current period is always calendar-aligned (1st of month/year).
-- ============================================================
CREATE TABLE budgets (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name       TEXT        NOT NULL,
    currency   CHAR(3)     NOT NULL DEFAULT 'EUR',
    period     TEXT        NOT NULL DEFAULT 'monthly'
                           CHECK (period IN ('monthly','yearly')),
    start_date DATE        NOT NULL DEFAULT CURRENT_DATE,
    is_active  BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- BUDGET CATEGORIES  (spending limit per category)
-- ============================================================
CREATE TABLE budget_categories (
    id           UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    budget_id    UUID          NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    category_id  UUID          NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    amount_limit NUMERIC(12,2) NOT NULL CHECK (amount_limit > 0),
    UNIQUE (budget_id, category_id)
);

-- ============================================================
-- BUDGET MEMBERS
-- owner  — created the budget, full control
-- member — contributes transactions, can view
-- viewer — read-only
-- Creator is auto-inserted as owner by trigger (see 002_rls.sql).
-- ============================================================
CREATE TABLE budget_members (
    id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    budget_id UUID NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    user_id   UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role      TEXT NOT NULL DEFAULT 'member'
                   CHECK (role IN ('owner','member','viewer')),
    UNIQUE (budget_id, user_id)
);

-- ============================================================
-- NOTIFICATIONS
-- ============================================================
CREATE TABLE notifications (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    type       TEXT        NOT NULL
                           CHECK (type IN ('budget_warning','budget_exceeded',
                                           'weekly_digest','anomaly_detected')),
    payload    JSONB       NOT NULL DEFAULT '{}',
    sent_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- QUERY LOG  (Telegram bot history)
-- ============================================================
CREATE TABLE query_log (
    id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    query_text    TEXT        NOT NULL,
    response_text TEXT,
    tokens_used   INT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX idx_transactions_user_date   ON transactions(user_id, date DESC);
CREATE INDEX idx_transactions_category    ON transactions(category_id);
CREATE INDEX idx_transactions_statement   ON transactions(statement_id);
CREATE INDEX idx_transactions_unreviewed  ON transactions(user_id, is_reviewed)
    WHERE NOT is_reviewed;
CREATE INDEX idx_transactions_source      ON transactions(classification_source);
CREATE INDEX idx_statements_user_status   ON statements(user_id, status);
CREATE INDEX idx_notifications_unsent     ON notifications(user_id)
    WHERE sent_at IS NULL;
CREATE INDEX idx_merchant_rules_user_prio ON merchant_rules(user_id, priority DESC);
CREATE INDEX idx_user_profiles_telegram   ON user_profiles(telegram_chat_id)
    WHERE telegram_chat_id IS NOT NULL;
CREATE INDEX idx_budgets_active           ON budgets(user_id) WHERE is_active = TRUE;
