"""
generate_ratings.py
Generates synthetic TV episode ratings data across three review sources
(IMDB, Rotten Tomatoes, Metacritic), each using a DIFFERENT rating scale,
plus deliberately seeded data quality issues that mirror real-world
problems in combining scores from multiple sources into one figure.

Show titles are used only as illustrative labels for synthetic numeric
data; no real ratings or review scores are represented. IMDB, Rotten
Tomatoes, and Metacritic are named only as realistic examples of the
kind of source a real version of this would pull from - no real data
from any of them is used or implied.
"""
import random
import csv
from datetime import date, timedelta

random.seed(21)

SHOW_IDS = {
    "The Big Bang Theory": "TBBT",
    "Brooklyn Nine-Nine": "B99",
    "Game of Thrones": "GOT",
    "The Office": "OFC",
    "Breaking Bad": "BRBA",
    "Parks and Recreation": "PARKS",
}

TITLE_VARIANTS = {
    "The Big Bang Theory": ["Big Bang Theory", "the big bang theory", "TBBT"],
    "Brooklyn Nine-Nine": ["Brooklyn 99", "brooklyn nine-nine", "Brooklyn Nine Nine"],
}

# Each source has its own native scale - this is the whole point of the
# project: you cannot average these numbers directly without converting
# them onto a common scale first.
SOURCES = {
    "imdb": {"scale": "0-10"},
    "rotten_tomatoes": {"scale": "0-100 (percent)"},
    "metacritic": {"scale": "0-100"},
}

def random_date(start_year=2018, end_year=2023):
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

# --- Show reference / crosswalk table ---
with open("show_reference.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["show_id", "canonical_title", "alias"])
    for title, show_id in SHOW_IDS.items():
        writer.writerow([show_id, title, title])
        for alias in TITLE_VARIANTS.get(title, []):
            writer.writerow([show_id, title, alias])

# --- Build the episode catalog ---
episode_catalog = []
for show, show_id in SHOW_IDS.items():
    for season in range(1, 4):
        for ep_num in range(1, 9):
            ep_id = f"{show_id}-S{season}E{ep_num}"
            air_dt = random_date()
            episode_catalog.append((ep_id, show, season, ep_num, air_dt))

# --- Generate one score submission per source per episode ---
rows = []
row_id = 1
for ep_id, show, season, ep_num, air_dt in episode_catalog:
    for source in SOURCES:
        if source == "imdb":
            raw_score = round(random.uniform(6.0, 9.5), 1)
        else:
            raw_score = round(random.uniform(55, 98), 0)

        rows.append({
            "record_id": f"REC{row_id:05d}",
            "episode_id": ep_id,
            "show_title": show,
            "season": season,
            "episode": ep_num,
            "source": source,
            "air_date": air_dt.isoformat(),
            "raw_score": raw_score,
        })
        row_id += 1

# --- Seed deliberate data quality issues ---

# 1. Title spelling/casing variants
variant_targets = [i for i, r in enumerate(rows) if r["show_title"] in TITLE_VARIANTS]
for idx in random.sample(variant_targets, min(10, len(variant_targets))):
    orig = rows[idx]["show_title"]
    rows[idx]["show_title"] = random.choice(TITLE_VARIANTS[orig])

# 2. Missing score
for idx in random.sample(range(len(rows)), 8):
    rows[idx]["raw_score"] = ""

# 3. Non-numeric garbage
for idx in random.sample(range(len(rows)), 3):
    rows[idx]["raw_score"] = "n/a"

# 4. Wrong-scale entry - the classic mistake: an IMDB score typed as if
#    it were a 0-100 score (85 instead of 8.5). This produces a value
#    that LOOKS plausible but is on the wrong scale entirely.
imdb_rows = [i for i, r in enumerate(rows) if r["source"] == "imdb" and r["raw_score"] != ""]
for idx in random.sample(imdb_rows, 5):
    correct = rows[idx]["raw_score"]
    if isinstance(correct, (int, float)):
        rows[idx]["raw_score"] = round(correct * 10, 0)  # 8.5 -> 85

# 5. Out-of-range score (impossible values regardless of scale)
for idx in random.sample(range(len(rows)), 4):
    rows[idx]["raw_score"] = random.choice([-5, 150, -1])

# 6. Duplicate submission - same source submits the same episode's score
#    twice, sometimes with a different value (a resend/pipeline issue).
dup_targets = random.sample(range(len(rows)), 12)
extra_rows = []
for idx in dup_targets:
    original = rows[idx]
    dup_score = original["raw_score"]
    if isinstance(dup_score, (int, float)) and random.random() < 0.4:
        dup_score = round(dup_score + random.choice([-3, 3]), 1)
    extra_rows.append({
        "record_id": f"REC{row_id:05d}",
        "episode_id": original["episode_id"],
        "show_title": original["show_title"],
        "season": original["season"],
        "episode": original["episode"],
        "source": original["source"],
        "air_date": original["air_date"],
        "raw_score": dup_score,
    })
    row_id += 1
rows.extend(extra_rows)

with open("ratings_raw.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} synthetic score submissions across {len(SHOW_IDS)} shows -> ratings_raw.csv")
print("Show reference / crosswalk table -> show_reference.csv")
