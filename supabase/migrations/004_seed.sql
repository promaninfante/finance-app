-- 13 system categories (user_id = NULL).
-- Visible to every authenticated user via the categories_select RLS policy.
INSERT INTO categories (user_id, name, color, icon, is_system) VALUES
    (NULL, 'Food & Dining',  '#F59E0B', 'utensils',     TRUE),
    (NULL, 'Transport',      '#3B82F6', 'car',           TRUE),
    (NULL, 'Groceries',      '#10B981', 'shopping-cart', TRUE),
    (NULL, 'Shopping',       '#8B5CF6', 'bag',           TRUE),
    (NULL, 'Health',         '#EF4444', 'heart',         TRUE),
    (NULL, 'Entertainment',  '#F97316', 'film',          TRUE),
    (NULL, 'Utilities',      '#6B7280', 'zap',           TRUE),
    (NULL, 'Rent & Housing', '#1D4ED8', 'home',          TRUE),
    (NULL, 'Subscriptions',  '#EC4899', 'repeat',        TRUE),
    (NULL, 'Travel',         '#0EA5E9', 'plane',         TRUE),
    (NULL, 'Income',         '#22C55E', 'trending-up',   TRUE),
    (NULL, 'Transfers',      '#94A3B8', 'arrows-h',      TRUE),
    (NULL, 'Other',          '#D1D5DB', 'tag',           TRUE)
ON CONFLICT DO NOTHING;
