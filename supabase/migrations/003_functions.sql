-- ============================================================
-- get_budget_progress(budget_id)
--
-- Returns per-category spend for the current auto-renewing period.
-- Runs as SECURITY DEFINER to read transactions across all budget
-- members, bypassing the strict per-user RLS on transactions.
-- Caller must be a member of the budget (enforced inside function).
--
-- Period is calendar-aligned:
--   monthly → 1st of the current month to last day of current month
--   yearly  → 1st Jan to 31st Dec of current year
--
-- Amounts: expenses are negative, so we ABS() and filter amount < 0.
-- ============================================================
CREATE OR REPLACE FUNCTION get_budget_progress(p_budget_id UUID)
RETURNS TABLE (
    category_id      UUID,
    category_name    TEXT,
    amount_limit     NUMERIC,
    amount_spent     NUMERIC,
    amount_remaining NUMERIC,
    period_start     DATE,
    period_end       DATE
)
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_period       TEXT;
    v_period_start DATE;
    v_period_end   DATE;
BEGIN
    -- Verify caller is a member of this budget
    IF NOT EXISTS (
        SELECT 1 FROM budget_members
        WHERE budget_id = p_budget_id AND user_id = auth.uid()
    ) THEN
        RAISE EXCEPTION 'Access denied to budget %', p_budget_id;
    END IF;

    SELECT period INTO v_period FROM budgets WHERE id = p_budget_id;

    IF v_period = 'monthly' THEN
        v_period_start := date_trunc('month', NOW())::date;
        v_period_end   := (date_trunc('month', NOW()) + interval '1 month - 1 day')::date;
    ELSE
        v_period_start := date_trunc('year', NOW())::date;
        v_period_end   := (date_trunc('year', NOW()) + interval '1 year - 1 day')::date;
    END IF;

    RETURN QUERY
    SELECT
        bc.category_id,
        c.name                                                              AS category_name,
        bc.amount_limit,
        COALESCE(ABS(SUM(t.amount) FILTER (WHERE t.amount < 0)), 0)        AS amount_spent,
        bc.amount_limit
            - COALESCE(ABS(SUM(t.amount) FILTER (WHERE t.amount < 0)), 0)  AS amount_remaining,
        v_period_start,
        v_period_end
    FROM budget_categories bc
    JOIN categories c ON c.id = bc.category_id
    LEFT JOIN transactions t
        ON  t.category_id = bc.category_id
        AND t.user_id     IN (
                SELECT user_id FROM budget_members WHERE budget_id = p_budget_id
            )
        AND t.date BETWEEN v_period_start AND v_period_end
    WHERE bc.budget_id = p_budget_id
    GROUP BY bc.category_id, c.name, bc.amount_limit;
END;
$$;
