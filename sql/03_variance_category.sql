-- Plan vs actual per ministry and economic category (Hauptgruppe).
CREATE OR REPLACE VIEW v_variance_category AS
SELECT f.account, f.year, f.ep_id, d.ep_label, f.hauptgruppe, h.hauptgruppe_label,
       sum(f.soll) AS soll, sum(f.ist) AS ist, sum(f.ist) - sum(f.soll) AS variance
FROM fact_titel f
JOIN dim_ep d USING (ep_id)
LEFT JOIN dim_hauptgruppe h ON h.account = f.account AND h.hauptgruppe = f.hauptgruppe
GROUP BY ALL;
