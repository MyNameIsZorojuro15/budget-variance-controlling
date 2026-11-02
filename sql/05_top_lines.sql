-- The budget lines with the largest absolute deviation per year and account.
CREATE OR REPLACE VIEW v_top_lines AS
SELECT *
FROM (
    SELECT f.account, f.year, f.ep_id, d.ep_label, f.kap_id, f.titel_id, f.hauptgruppe, f.titel_label,
           f.soll, f.ist, f.variance, f.line_status,
           row_number() OVER (PARTITION BY f.account, f.year ORDER BY abs(f.variance) DESC) AS rnk
    FROM fact_titel f JOIN dim_ep d USING (ep_id)
)
WHERE rnk <= 50;
