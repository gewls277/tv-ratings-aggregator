-- reconcile.sql
-- Data quality checks plus the actual combined-score calculation,
-- written as real SQL against the ratings table.
--
-- Two supporting views are created by run_sql_reconciliation.py before
-- these queries run (view_valid_scores holds rows that pass all quality
-- checks, view_normalized converts those rows onto a common 0-100
-- scale with the canonical show title resolved). Query 1 (IS_VALID_NUMBER)
-- also depends on a custom function registered by that same script - see
-- its docstring for why plain SQLite CAST() isn't safe to rely on here.

-- 1. Missing or non-numeric score.
SELECT record_id, episode_id, show_title, source, raw_score
FROM ratings
WHERE TRIM(raw_score) = '' OR NOT IS_VALID_NUMBER(raw_score);

-- 2. Out-of-range score for the source's own scale - this also catches
--    the classic "typed 85 instead of 8.5" wrong-scale mistake, since a
--    wrong-scale IMDB value of 85 is out of IMDB's 0-10 range.
SELECT record_id, episode_id, source, raw_score,
       CASE source
           WHEN 'imdb' THEN '0-10'
           ELSE '0-100'
       END AS expected_range
FROM ratings
WHERE IS_VALID_NUMBER(raw_score)
  AND (
    (source = 'imdb' AND (CAST(raw_score AS REAL) < 0 OR CAST(raw_score AS REAL) > 10))
    OR (source != 'imdb' AND (CAST(raw_score AS REAL) < 0 OR CAST(raw_score AS REAL) > 100))
  );

-- 3. Duplicate submissions - same source, same episode, more than once.
SELECT episode_id, source, COUNT(*) AS submission_count
FROM ratings
GROUP BY episode_id, source
HAVING COUNT(*) > 1
ORDER BY submission_count DESC;

-- 4. Show titles that don't match any known alias in the crosswalk.
SELECT DISTINCT r.show_title
FROM ratings r
LEFT JOIN show_reference ref ON r.show_title = ref.alias
WHERE ref.alias IS NULL;

-- 5. Combined score per episode (built from view_normalized, which
--    already excludes bad values and collapses duplicates to the
--    latest submission).
SELECT episode_id, canonical_title, season, episode,
       ROUND(AVG(normalized_score), 1) AS combined_score,
       COUNT(*) AS sources_used
FROM view_normalized
GROUP BY episode_id, canonical_title, season, episode
ORDER BY episode_id
LIMIT 10;

-- 6. Combined score per season - a further aggregation on top of the
--    per-episode combined scores.
SELECT canonical_title, season,
       ROUND(AVG(ep_score), 1) AS season_score,
       COUNT(*) AS episodes_scored
FROM (
    SELECT episode_id, canonical_title, season,
           AVG(normalized_score) AS ep_score
    FROM view_normalized
    GROUP BY episode_id, canonical_title, season
)
GROUP BY canonical_title, season
ORDER BY canonical_title, season;

-- 7. Episodes whose combined score is based on fewer than all 3
--    sources - worth knowing about even though it isn't an error.
SELECT episode_id, canonical_title, COUNT(*) AS sources_used
FROM view_normalized
GROUP BY episode_id, canonical_title
HAVING COUNT(*) < 3;
