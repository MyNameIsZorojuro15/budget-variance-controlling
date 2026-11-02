-- Execution ratio Ist / Soll per ministry and year (expenses): the input of the forecast.
CREATE OR REPLACE VIEW v_execution_ratio AS
SELECT ep_id, ep_label, year, soll, ist, ist / soll AS exec_ratio
FROM v_variance_ep
WHERE account = 'expenses' AND soll > 0;
