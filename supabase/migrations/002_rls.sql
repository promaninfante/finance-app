-- ============================================================
-- TRIGGER: auto-create user_profiles row on signup
-- ============================================================
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    INSERT INTO public.user_profiles (id)
    VALUES (NEW.id)
    ON CONFLICT DO NOTHING;
    RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ============================================================
-- TRIGGER: auto-insert budget creator as owner in budget_members
-- ============================================================
CREATE OR REPLACE FUNCTION handle_new_budget()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    INSERT INTO public.budget_members (budget_id, user_id, role)
    VALUES (NEW.id, NEW.user_id, 'owner')
    ON CONFLICT DO NOTHING;
    RETURN NEW;
END;
$$;

CREATE TRIGGER on_budget_created
    AFTER INSERT ON budgets
    FOR EACH ROW EXECUTE FUNCTION handle_new_budget();

-- ============================================================
-- TRIGGER: maintain updated_at on transactions
-- ============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER transactions_updated_at
    BEFORE UPDATE ON transactions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- ENABLE RLS
-- ============================================================
ALTER TABLE user_profiles     ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories        ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts          ENABLE ROW LEVEL SECURITY;
ALTER TABLE statements        ENABLE ROW LEVEL SECURITY;
ALTER TABLE merchants         ENABLE ROW LEVEL SECURITY;
ALTER TABLE merchant_rules    ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions      ENABLE ROW LEVEL SECURITY;
ALTER TABLE budgets           ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget_members    ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications     ENABLE ROW LEVEL SECURITY;
ALTER TABLE query_log         ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- user_profiles — user sees and edits only their own row
-- ============================================================
CREATE POLICY "user_profiles_all" ON user_profiles
    USING (id = auth.uid()) WITH CHECK (id = auth.uid());

-- ============================================================
-- categories — see system rows (user_id IS NULL) + own rows
-- ============================================================
CREATE POLICY "categories_select" ON categories
    FOR SELECT USING (user_id IS NULL OR user_id = auth.uid());

CREATE POLICY "categories_insert" ON categories
    FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY "categories_update" ON categories
    FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

CREATE POLICY "categories_delete" ON categories
    FOR DELETE USING (user_id = auth.uid() AND is_system = FALSE);

-- ============================================================
-- accounts
-- ============================================================
CREATE POLICY "accounts_all" ON accounts
    USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- ============================================================
-- statements
-- ============================================================
CREATE POLICY "statements_all" ON statements
    USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- ============================================================
-- merchants — read for all authenticated; writes via service role only
-- ============================================================
CREATE POLICY "merchants_select" ON merchants
    FOR SELECT TO authenticated USING (TRUE);

-- ============================================================
-- merchant_rules
-- ============================================================
CREATE POLICY "merchant_rules_all" ON merchant_rules
    USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- ============================================================
-- transactions — strict per-user; cross-user reads via RPC only
-- ============================================================
CREATE POLICY "transactions_all" ON transactions
    USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- ============================================================
-- budgets — owner and all members can read; only owner can write
-- ============================================================
CREATE POLICY "budgets_select" ON budgets
    FOR SELECT USING (
        user_id = auth.uid()
        OR id IN (SELECT budget_id FROM budget_members WHERE user_id = auth.uid())
    );

CREATE POLICY "budgets_insert" ON budgets
    FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY "budgets_update" ON budgets
    FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

CREATE POLICY "budgets_delete" ON budgets
    FOR DELETE USING (user_id = auth.uid());

-- ============================================================
-- budget_categories
-- ============================================================
CREATE POLICY "budget_categories_select" ON budget_categories
    FOR SELECT USING (
        budget_id IN (SELECT id FROM budgets WHERE user_id = auth.uid())
        OR budget_id IN (SELECT budget_id FROM budget_members WHERE user_id = auth.uid())
    );

CREATE POLICY "budget_categories_write" ON budget_categories
    FOR ALL
    USING   (budget_id IN (SELECT id FROM budgets WHERE user_id = auth.uid()))
    WITH CHECK (budget_id IN (SELECT id FROM budgets WHERE user_id = auth.uid()));

-- ============================================================
-- budget_members
-- ============================================================
CREATE POLICY "budget_members_select" ON budget_members
    FOR SELECT USING (
        budget_id IN (SELECT id FROM budgets WHERE user_id = auth.uid())
        OR user_id = auth.uid()
    );

CREATE POLICY "budget_members_insert" ON budget_members
    FOR INSERT WITH CHECK (
        budget_id IN (SELECT id FROM budgets WHERE user_id = auth.uid())
    );

CREATE POLICY "budget_members_delete" ON budget_members
    FOR DELETE USING (
        budget_id IN (SELECT id FROM budgets WHERE user_id = auth.uid())
    );

-- ============================================================
-- notifications
-- ============================================================
CREATE POLICY "notifications_all" ON notifications
    USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- ============================================================
-- query_log
-- ============================================================
CREATE POLICY "query_log_all" ON query_log
    USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
