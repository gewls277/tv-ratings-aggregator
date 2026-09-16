"""
load_to_sqlite.py
Loads the synthetic ratings_raw.csv and show_reference.csv into a local
SQLite database so the checks and the combined-score calculation can
also be run as real SQL against real tables.
"""
import csv
import sqlite3

DB_PATH = "ratings.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS ratings")
cur.execute("""
    CREATE TABLE ratings (
        record_id TEXT, episode_id TEXT, show_title TEXT,
        season INTEGER, episode INTEGER, source TEXT,
        air_date TEXT, raw_score TEXT
    )
""")
with open("ratings_raw.csv", newline="") as f:
    reader = csv.DictReader(f)
    rows = [tuple(r[c] for c in ["record_id","episode_id","show_title","season","episode","source","air_date","raw_score"]) for r in reader]
cur.executemany("INSERT INTO ratings VALUES (?,?,?,?,?,?,?,?)", rows)

cur.execute("DROP TABLE IF EXISTS show_reference")
cur.execute("CREATE TABLE show_reference (show_id TEXT, canonical_title TEXT, alias TEXT)")
with open("show_reference.csv", newline="") as f:
    reader = csv.DictReader(f)
    ref_rows = [(r["show_id"], r["canonical_title"], r["alias"]) for r in reader]
cur.executemany("INSERT INTO show_reference VALUES (?,?,?)", ref_rows)

conn.commit()
print(f"Loaded {len(rows)} score submissions and {len(ref_rows)} crosswalk rows into {DB_PATH}")
conn.close()
