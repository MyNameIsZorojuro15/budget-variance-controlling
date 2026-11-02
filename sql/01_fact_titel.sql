-- One row per budget line (Titel), plan (Soll) next to actual (Ist).
-- Titel id = Kapitel (4 digits) + Titel number (3 digits) + sub-number (2 digits).
-- The first digit of the Titel number is the Hauptgruppe, the economic category
-- (expenses: 4 personnel ... 9 special financing; income: 0 taxes ... 3 loans).
CREATE OR REPLACE TABLE fact_titel AS
WITH t AS (
    SELECT year, quota, account, id AS titel_id, parent_id AS kap_id,
           substr(id, 1, 2) AS ep_id,
           substr(id, 5, 1) AS hauptgruppe,
           regexp_replace(label, '^[0-9]{4} [0-9]{3} [0-9]{2} ', '') AS titel_label,
           value
    FROM nodes
    WHERE level = 3
)
SELECT coalesce(s.year, i.year)             AS year,
       coalesce(s.account, i.account)       AS account,
       coalesce(s.titel_id, i.titel_id)     AS titel_id,
       coalesce(s.kap_id, i.kap_id)         AS kap_id,
       coalesce(s.ep_id, i.ep_id)           AS ep_id,
       coalesce(s.hauptgruppe, i.hauptgruppe) AS hauptgruppe,
       coalesce(i.titel_label, s.titel_label) AS titel_label,
       coalesce(s.value, 0.0)               AS soll,
       coalesce(i.value, 0.0)               AS ist,
       coalesce(i.value, 0.0) - coalesce(s.value, 0.0) AS variance,
       CASE WHEN s.titel_id IS NULL THEN 'ist_only'
            WHEN i.titel_id IS NULL THEN 'soll_only'
            ELSE 'both' END                 AS line_status
FROM (SELECT * FROM t WHERE quota = 'target') s
FULL OUTER JOIN (SELECT * FROM t WHERE quota = 'actual') i
  ON s.year = i.year AND s.account = i.account AND s.titel_id = i.titel_id;

-- Ministry (Einzelplan) and chapter names, latest label wins.
CREATE OR REPLACE TABLE dim_ep AS
SELECT substr(id, 1, 2) AS ep_id,
       arg_max(regexp_replace(label, '^[0-9]{2} ', ''), year) AS ep_label
FROM nodes WHERE level = 1 GROUP BY 1;

CREATE OR REPLACE TABLE dim_hauptgruppe AS
SELECT account, replace(group_id, 'G-', '') AS hauptgruppe,
       arg_max(regexp_replace(label, '^[0-9] ', ''), year) AS hauptgruppe_label
FROM group_totals GROUP BY 1, 2;
