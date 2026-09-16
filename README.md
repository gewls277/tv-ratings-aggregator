# TV Show Combined Ratings Aggregator

A small, self-contained prototype that combines TV episode ratings from
three review sources (IMDB, Rotten Tomatoes, and Metacritic) into one
overall score per episode and per season - synthetic data, built to
show method. No real ratings, review scores, or data from any of these
three sites is used or implied; they're named only as realistic,
recognizable examples of the kind of source a real version of this
would pull from.

## Why this exists

Any time you're combining a metric from more than one source, you run
into the same problem twice: first, the sources often don't even use
the same scale (IMDB rates out of 10, Rotten Tomatoes and Metacritic
are both out of 100 but measure different things), so you can't average
them directly without converting them onto common ground first. Second,
real source data is messy - missing values, values on the wrong scale
entirely (someone typing "85" into a 0-10 field), duplicate submissions
from a retry - and all of that needs to be caught *before* it can quietly
corrupt an average that looks fine on the surface.

That's the same category of problem I work on daily in enterprise data
operations - normalizing and combining figures from multiple systems
into one trustworthy number - applied here to something I actually enjoy
rather than a generic dataset.

## What it does

1. **`generate_ratings.py`** - builds a synthetic dataset of episode
   score submissions across 6 shows, 3 seasons, 8 episodes each, from
   three sources with three different native scales. Deliberately seeds
   realistic problems: missing scores, non-numeric garbage, wrong-scale
   entries (an IMDB score entered as if it were 0-100), out-of-range
   values, duplicate submissions, and inconsistent show title spellings.
2. **`show_reference.csv`** - a small crosswalk mapping title spelling
   variants to a canonical show ID, so an episode's combined score isn't
   accidentally split across several "different" episodes just because
   its title was spelled inconsistently across submissions.
3. **`validate_ratings.py`** - a Python/pandas engine that (a) flags
   every data quality issue above, then (b) excludes anything bad,
   collapses duplicates to the latest submission, converts every score
   onto a common 0-100 scale, and computes a combined score per episode
   and per season - reporting transparently how many of the 3 sources
   each combined score is actually based on.
4. **`load_to_sqlite.py`** / **`reconcile.sql`** / **`run_sql_reconciliation.py`**
   - the same two-stage process (quality checks, then normalize and
   combine) re-implemented as standalone SQL against a local SQLite
   database, with results cross-checked against the Python output.

## A bug I found and fixed while building this

The first version of the aggregation step grouped episodes by their raw
show title instead of by a canonical ID. Because a handful of episodes
had inconsistently-spelled titles by design (that's one of the seeded
data quality issues), those episodes were being split into two or three
separate "episodes" - one per spelling - each with its own partial,
wrong combined score, instead of being recognized as the same episode
with all three sources correctly combined. Fixed by joining against the
show reference crosswalk and grouping by canonical title instead of the
raw one. Worth naming rather than hiding, since catching this kind of
thing is a real part of the job this project is meant to demonstrate.

## Sample output - Python/pandas run

```
Total score submissions processed: 444
Records with an exception:          176
Total exceptions raised:             193

Exceptions by rule:
  INCONSISTENT_SHOW_TITLE       148
  DUPLICATE_SUBMISSION           24
  MISSING_OR_INVALID_SCORE       11
  SCORE_OUT_OF_RANGE             10

Episodes with a combined score: 144
  ...of which based on fewer than 3 sources: 19
Seasons scored: 18
```

## Sample query (episode combined score)

```sql
SELECT episode_id, canonical_title, season, episode,
       ROUND(AVG(normalized_score), 1) AS combined_score,
       COUNT(*) AS sources_used
FROM view_normalized
GROUP BY episode_id, canonical_title, season, episode
ORDER BY episode_id;
```

## Design notes

- **Normalization happens before aggregation, always.** IMDB's 0-10
  score is multiplied by 10 before anything is averaged; Rotten Tomatoes
  and Metacritic are already 0-100. Averaging the raw numbers without
  this step would silently and badly under-weight IMDB in every combined
  score.
- **A missing or bad source doesn't sink the whole episode.** If only 2
  of 3 sources have a valid score, the combined score is calculated from
  those 2 - and `sources_used` makes that visible rather than hiding it,
  so nobody mistakes a 2-source score for a full one.
- **Duplicates are resolved, not just flagged.** A source resubmitting
  the same episode is caught as a data quality issue *and* handled
  correctly in the actual calculation (only the latest submission counts),
  rather than being left as an open problem for someone else to fix.
- **Python and SQL are cross-checked.** Every combined score in this
  README came from the pandas engine; running the SQL version against
  the same data produces the identical numbers.

## Run it yourself

Python/pandas version:
```
pip install pandas
python3 generate_ratings.py
python3 validate_ratings.py
```

SQL version:
```
python3 load_to_sqlite.py
python3 run_sql_reconciliation.py
```

## Files

- `generate_ratings.py` - synthetic multi-source score generator
- `show_reference.csv` - show-ID crosswalk (title aliases to canonical ID)
- `validate_ratings.py` - Python/pandas quality checks + score aggregation
- `load_to_sqlite.py` - loads the data into a local SQLite database
- `reconcile.sql` - standalone SQL quality checks + score aggregation
- `run_sql_reconciliation.py` - sets up views/functions, runs the SQL, prints results
- `ratings_raw.csv` - generated input data
- `exception_queue.csv` - flagged records with rule, detail, and severity
- `episode_scores.csv` - combined score per episode
- `season_scores.csv` - combined score per season
- `summary_report.txt` - pandas run summary

---
*All data in this project is synthetic and fictional, generated for
demonstration purposes. IMDB, Rotten Tomatoes, and Metacritic are named
only as realistic examples of review sources - no real data from any of
them is used or implied.*
