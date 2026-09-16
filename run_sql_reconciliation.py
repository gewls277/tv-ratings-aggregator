"""
run_sql_reconciliation.py
Sets up two views (valid, quality-checked rows; those rows normalized
onto a common scale with canonical titles resolved), registers a
validation function plain SQLite can't do safely on its own, then runs
every query in reconcile.sql and prints the results.
"""
import sqlite3
import re

DB_PATH = "ratings.db"
SQL_PATH = "reconcile.sql"

NUMBER_RE = re.compile(r"^-?\d+(\.\d+)?$")

def is_valid_number(text):
    if text is None:
        return 0
    return 1 if NUMBER_RE.match(text.strip()) else 0

conn = sqlite3.connect(DB_PATH)
conn.create_function("IS_VALID_NUMBER", 1, is_valid_number)
cur = conn.cursor()

# --- Setup views (infrastructure, not shown as "the SQL skill" content -
# that's what reconcile.sql itself is for) ---
cur.executescript("""
DROP VIEW IF EXISTS view_valid_scores;
CREATE VIEW view_valid_scores AS
SELECT r.*,
       ROW_NUMBER() OVER (PARTITION BY episode_id, source ORDER BY record_id DESC) AS rn
FROM ratings r
WHERE TRIM(raw_score) != ''
  AND IS_VALID_NUMBER(raw_score)
  AND (
    (source = 'imdb' AND CAST(raw_score AS REAL) BETWEEN 0 AND 10)
    OR (source != 'imdb' AND CAST(raw_score AS REAL) BETWEEN 0 AND 100)
  );

DROP VIEW IF EXISTS view_normalized;
CREATE VIEW view_normalized AS
SELECT
    v.episode_id, v.season, v.episode,
    COALESCE(ref.canonical_title, v.show_title) AS canonical_title,
    CASE WHEN v.source = 'imdb' THEN CAST(v.raw_score AS REAL) * 10
         ELSE CAST(v.raw_score AS REAL) END AS normalized_score
FROM view_valid_scores v
LEFT JOIN show_reference ref ON v.show_title = ref.alias
WHERE v.rn = 1;
""")

def load_queries(path):
    with open(path) as f:
        content = f.read()
    # Split on blank lines rather than semicolons - a semicolon can
    # legitimately appear inside a comment's prose (it did, in an
    # earlier draft of this file, and broke a naive split(';') parser).
    # Blank lines reliably separate one labeled query from the next here.
    blocks = [b.strip() for b in content.split("\n\n") if b.strip()]
    return blocks[1:]  # blocks[0] is the file's header comment, not a query

def label_for(block):
    lines = [l.strip() for l in block.splitlines() if l.strip().startswith("--")]
    return lines[-1].lstrip("-").strip() if lines else "(query)"

queries = load_queries(SQL_PATH)
print("SQL RECONCILIATION RESULTS")
print("=" * 60)

for block in queries:
    label = label_for(block)
    stmt_lines = [l for l in block.splitlines() if not l.strip().startswith("--")]
    stmt = "\n".join(stmt_lines).strip().rstrip(";")
    if not stmt:
        continue
    cur.execute(stmt)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    print(f"\n{label}")
    print("-" * len(label))
    print(f"Rows returned: {len(rows)}")
    if rows:
        print("Columns:", ", ".join(cols))
        for r in rows[:5]:
            print("  ", r)
        if len(rows) > 5:
            print(f"   ... and {len(rows) - 5} more")

conn.close()
