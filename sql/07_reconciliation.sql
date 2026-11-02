-- Reconciliation checks. Every view lists only the rows that BREAK the rule; an empty view is a pass.
-- A tolerance of EUR 1 absorbs float rounding on sums of values stored to the cent.

-- R1: reported parent value = sum of its children, at every level of the plan.
CREATE OR REPLACE VIEW chk_level_sums AS
WITH child AS (
    SELECT year, quota, account, level - 1 AS parent_level, parent_id AS id, sum(value) AS child_sum
    FROM nodes WHERE level >= 1 GROUP BY ALL
)
SELECT p.year, p.quota, p.account, p.level, p.id, p.value AS reported,
       coalesce(c.child_sum, 0) AS child_sum, p.value - coalesce(c.child_sum, 0) AS diff
FROM nodes p
LEFT JOIN child c ON c.year = p.year AND c.quota = p.quota AND c.account = p.account
                 AND c.parent_level = p.level AND c.id = p.id
WHERE p.level < 3 AND abs(p.value - coalesce(c.child_sum, 0)) > 1.0;

-- R2: line-item totals per category tie to the source's own category view (independent aggregation).
CREATE OR REPLACE VIEW chk_group_totals AS
WITH lines AS (
    SELECT year, quota, account, substr(id, 5, 1) AS hauptgruppe, sum(value) AS line_sum
    FROM nodes WHERE level = 3 GROUP BY ALL
)
SELECT g.year, g.quota, g.account, replace(g.group_id, 'G-', '') AS hauptgruppe,
       g.value AS reported, coalesce(l.line_sum, 0) AS line_sum, g.value - coalesce(l.line_sum, 0) AS diff
FROM group_totals g
LEFT JOIN lines l ON l.year = g.year AND l.quota = g.quota AND l.account = g.account
                 AND l.hauptgruppe = replace(g.group_id, 'G-', '')
WHERE abs(g.value - coalesce(l.line_sum, 0)) > 1.0;

-- R3: the federal budget is balanced by law: total expenses = total income, for plan and actual.
CREATE OR REPLACE VIEW chk_balance AS
SELECT e.year, e.quota, e.value AS expenses, i.value AS income, e.value - i.value AS diff
FROM nodes e JOIN nodes i ON e.year = i.year AND e.quota = i.quota AND e.level = 0 AND i.level = 0
WHERE e.account = 'expenses' AND i.account = 'income' AND abs(e.value - i.value) > 1.0;

-- R4: no orphans / missing codes: every line's code prefix matches its parent, every parent exists.
CREATE OR REPLACE VIEW chk_orphans AS
SELECT n.year, n.quota, n.account, n.level, n.id, n.parent_id
FROM nodes n
LEFT JOIN nodes p ON p.year = n.year AND p.quota = n.quota AND p.account = n.account
                 AND p.level = n.level - 1 AND p.id = n.parent_id
WHERE n.level >= 1 AND p.id IS NULL
UNION ALL
SELECT year, quota, account, level, id, parent_id
FROM nodes
WHERE (level = 2 AND substr(id, 1, 2) <> parent_id)
   OR (level = 3 AND substr(id, 1, 4) <> parent_id)
   OR (level = 3 AND length(id) <> 9)
   OR (level = 2 AND length(id) <> 4)
   OR (level = 1 AND length(id) <> 2);

-- R5: duplicate keys.
CREATE OR REPLACE VIEW chk_duplicates AS
SELECT year, quota, account, level, id, count(*) AS n
FROM nodes GROUP BY ALL HAVING count(*) > 1;

-- R6: category code must be valid for the account (expenses 4-9, income 0-3).
CREATE OR REPLACE VIEW chk_category_codes AS
SELECT year, quota, account, id, substr(id, 5, 1) AS hauptgruppe
FROM nodes
WHERE level = 3 AND ((account = 'expenses' AND substr(id, 5, 1) NOT IN ('4','5','6','7','8','9'))
                  OR (account = 'income'   AND substr(id, 5, 1) NOT IN ('0','1','2','3')));

-- R7: sign check. Expense lines should not be negative (refunds and negative reserves are the exception);
-- the view lists every negative expense line so that their weight can be judged.
CREATE OR REPLACE VIEW chk_negative_expense_lines AS
SELECT year, quota, id, label, value
FROM nodes WHERE level = 3 AND account = 'expenses' AND value < 0;

-- R7b: sign check with a documented allow-list. A negative expense line above EUR 1 bn is only plausible if it is
-- (a) a global savings target in the plan, (b) a bond discount (negative interest cost, issued above par)
-- or (c) a refund of Covid aid. Any other large negative expense line is flagged for review.
CREATE OR REPLACE VIEW chk_unexplained_negative_lines AS
SELECT year, quota, id, label, value
FROM chk_negative_expense_lines
WHERE value < -1e9
  AND NOT regexp_matches(label, 'Globale Minderausgabe|Disagio|Diskont|Corona-Soforthilfen');

-- R8: coverage: every year has plan and actual for both accounts.
CREATE OR REPLACE VIEW chk_coverage AS
SELECT y.year, q.quota, a.account
FROM (SELECT DISTINCT year FROM nodes) y CROSS JOIN (SELECT DISTINCT quota FROM nodes) q
     CROSS JOIN (SELECT DISTINCT account FROM nodes) a
LEFT JOIN nodes n ON n.year = y.year AND n.quota = q.quota AND n.account = a.account AND n.level = 0
WHERE n.id IS NULL;
