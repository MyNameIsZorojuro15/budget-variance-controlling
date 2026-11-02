-- Plan vs actual per ministry (Einzelplan) and year. Variance = Ist - Soll.
-- Expenses: negative = under-spend. Income: negative = revenue shortfall.
CREATE OR REPLACE VIEW v_variance_ep AS
SELECT f.account, f.year, f.ep_id, d.ep_label,
       sum(f.soll)     AS soll,
       sum(f.ist)      AS ist,
       sum(f.ist) - sum(f.soll) AS variance,
       CASE WHEN sum(f.soll) <> 0 THEN (sum(f.ist) - sum(f.soll)) / sum(f.soll) END AS variance_pct,
       count(*)        AS lines
FROM fact_titel f JOIN dim_ep d USING (ep_id)
GROUP BY f.account, f.year, f.ep_id, d.ep_label;
