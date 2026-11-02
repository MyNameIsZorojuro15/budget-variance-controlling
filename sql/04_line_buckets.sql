-- Driver split of the variance: every budget line falls into exactly one bucket, so the buckets add up
-- to the total variance.
--   planned_and_booked  in the plan and booked: the spending rate differs from plan
--   planned_not_booked  in the plan with a positive amount, nothing booked (unused provisions, cancelled measures)
--   savings_target      negative plan lines (global savings targets): they are never booked as such, so
--                       they always show up as a positive variance of the same size
--   unplanned           booked on a line that has no plan entry for the year (carried-over funds, new lines)
--   renumbered          an unplanned and a planned-not-booked line with the same ministry and the same title text
--                       in the same year: the item moved to another line number, its variance is the net of both
CREATE OR REPLACE VIEW v_line_buckets AS
WITH base AS (
    SELECT f.*,
           CASE WHEN line_status = 'ist_only'   THEN 'unplanned'
                WHEN soll < 0                   THEN 'savings_target'
                WHEN line_status = 'soll_only'  THEN 'planned_not_booked'
                ELSE 'planned_and_booked' END AS raw_bucket
    FROM fact_titel f
),
flagged AS (
    SELECT *,
           bool_or(raw_bucket = 'unplanned')          OVER w AS has_unplanned,
           bool_or(raw_bucket = 'planned_not_booked') OVER w AS has_not_booked
    FROM base
    WINDOW w AS (PARTITION BY account, year, ep_id, titel_label)
)
SELECT account, year, ep_id, kap_id, titel_id, hauptgruppe, titel_label, soll, ist, variance, line_status,
       CASE WHEN raw_bucket IN ('unplanned', 'planned_not_booked') AND has_unplanned AND has_not_booked
            THEN 'renumbered' ELSE raw_bucket END AS bucket
FROM flagged;

CREATE OR REPLACE VIEW v_bucket_summary AS
SELECT account, year, bucket, count(*) AS lines,
       sum(soll) AS soll, sum(ist) AS ist, sum(variance) AS variance
FROM v_line_buckets
GROUP BY ALL;
