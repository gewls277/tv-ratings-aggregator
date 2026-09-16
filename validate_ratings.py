"""
validate_ratings.py
Two jobs in one script, both realistic parts of the same real-world task:

1. DATA QUALITY: find missing, invalid, out-of-range, wrong-scale, and
   duplicate score submissions before they can corrupt an aggregate.
2. AGGREGATION: normalize the three sources (IMDB 0-10, Rotten Tomatoes
   0-100%, Metacritic 0-100) onto one common 0-100 scale, then compute
   a combined score per episode and per season - using only the valid
   submissions, and being transparent about how many sources each
   combined score is actually based on.
"""
import pandas as pd

EXPECTED_SOURCES = {"imdb", "rotten_tomatoes", "metacritic"}
SCALE_BOUNDS = {
    "imdb": (0, 10),
    "rotten_tomatoes": (0, 100),
    "metacritic": (0, 100),
}
EXCEPTION_COLUMNS = ["record_id", "episode_id", "show_title", "source", "rule", "detail", "severity"]
SEVERITY_ORDER = ["High", "Medium", "Low"]

df = pd.read_csv("ratings_raw.csv", dtype=str, keep_default_na=False)
df["raw_score_num"] = pd.to_numeric(df["raw_score"], errors="coerce")

exceptions = []

def flag(row, rule, detail, severity="High"):
    exceptions.append({
        "record_id": row["record_id"], "episode_id": row["episode_id"],
        "show_title": row["show_title"], "source": row["source"],
        "rule": rule, "detail": detail, "severity": severity,
    })

# --- Duplicate submissions: same source, same episode, more than once ---
dup_counts = df.groupby(["episode_id", "source"])["record_id"].transform("count")
for _, row in df[dup_counts > 1].iterrows():
    flag(row, "DUPLICATE_SUBMISSION",
         f"Source '{row['source']}' submitted a score for '{row['episode_id']}' more than once",
         "Medium")

# --- Inconsistent show title for the same show ID ---
df["show_prefix"] = df["episode_id"].str.split("-").str[0]
prefix_titles = df.groupby("show_prefix")["show_title"].apply(lambda s: sorted(set(s)))
inconsistent = {k: v for k, v in prefix_titles.items() if len(v) > 1}
for _, row in df.iterrows():
    if row["show_prefix"] in inconsistent:
        flag(row, "INCONSISTENT_SHOW_TITLE",
             f"Show ID '{row['show_prefix']}' maps to multiple title spellings: {inconsistent[row['show_prefix']]}",
             "Low")

# --- Missing or non-numeric score ---
bad_value = df[df["raw_score"].str.strip().eq("") | df["raw_score_num"].isna()]
for _, row in bad_value.iterrows():
    flag(row, "MISSING_OR_INVALID_SCORE", "raw_score is blank or not a valid number", "High")

# --- Out-of-range for the source's own scale (catches wrong-scale entries too) ---
def out_of_range(row):
    if pd.isna(row["raw_score_num"]):
        return False
    lo, hi = SCALE_BOUNDS[row["source"]]
    return row["raw_score_num"] < lo or row["raw_score_num"] > hi

for _, row in df[df.apply(out_of_range, axis=1)].iterrows():
    lo, hi = SCALE_BOUNDS[row["source"]]
    flag(row, "SCORE_OUT_OF_RANGE",
         f"{row['raw_score']} is outside the valid {row['source']} range ({lo}-{hi}) - check for a wrong-scale entry",
         "High")

# --- Build exception queue ---
exc_df = pd.DataFrame(exceptions, columns=EXCEPTION_COLUMNS)
if not exc_df.empty:
    exc_df["severity"] = pd.Categorical(exc_df["severity"], categories=SEVERITY_ORDER, ordered=True)
    exc_df = exc_df.sort_values(["severity", "rule", "record_id"])
exc_df.to_csv("exception_queue.csv", index=False)

# --- Combined score calculation ---
# Only valid, in-range submissions are used. Duplicates are collapsed to
# their most recent value so a resend doesn't double-count. Grouping is
# done by episode_id (and the canonical show title from the reference
# crosswalk) rather than the raw show_title column - grouping by raw
# show_title would split the same episode into several fake "episodes"
# whenever its title was spelled inconsistently across submissions,
# which defeats the purpose of having a title crosswalk at all.
bad_record_ids = set(exc_df[exc_df["rule"].isin(["MISSING_OR_INVALID_SCORE", "SCORE_OUT_OF_RANGE"])]["record_id"]) if not exc_df.empty else set()
clean = df[~df["record_id"].isin(bad_record_ids)].copy()
clean = clean.drop_duplicates(subset=["episode_id", "source"], keep="last")

ref = pd.read_csv("show_reference.csv", dtype=str)
alias_to_canonical = dict(zip(ref["alias"], ref["canonical_title"]))
clean["canonical_title"] = clean["show_title"].map(alias_to_canonical).fillna(clean["show_title"])

def normalize(row):
    if row["source"] == "imdb":
        return row["raw_score_num"] * 10
    return row["raw_score_num"]  # rotten_tomatoes and metacritic are already 0-100

clean["normalized_score"] = clean.apply(normalize, axis=1)

episode_scores = (
    clean.groupby(["episode_id", "canonical_title", "season", "episode"])
    .agg(combined_score=("normalized_score", "mean"), sources_used=("source", "nunique"))
    .reset_index()
    .rename(columns={"canonical_title": "show_title"})
)
episode_scores["combined_score"] = episode_scores["combined_score"].round(1)
episode_scores.to_csv("episode_scores.csv", index=False)

season_scores = (
    episode_scores.groupby(["show_title", "season"])
    .agg(season_score=("combined_score", "mean"), episodes_scored=("episode_id", "nunique"))
    .reset_index()
)
season_scores["season_score"] = season_scores["season_score"].round(1)
season_scores.to_csv("season_scores.csv", index=False)

# --- Summary ---
total_records = len(df)
records_with_exceptions = exc_df["record_id"].nunique() if not exc_df.empty else 0
lines = []
lines.append("TV RATINGS AGGREGATION SUMMARY")
lines.append("=" * 45)
lines.append(f"Total score submissions processed: {total_records}")
lines.append(f"Records with an exception:          {records_with_exceptions}")
lines.append(f"Total exceptions raised:             {len(exc_df)}")
lines.append("")
lines.append("Exceptions by rule:")
if not exc_df.empty:
    for rule, count in exc_df.groupby("rule", observed=True).size().sort_values(ascending=False).items():
        lines.append(f"  {rule:<28} {count:>4}")
lines.append("")
lines.append(f"Episodes with a combined score: {len(episode_scores)}")
partial = (episode_scores["sources_used"] < 3).sum()
lines.append(f"  ...of which based on fewer than 3 sources: {partial}")
lines.append(f"Seasons scored: {len(season_scores)}")
lines.append("")
lines.append("Sample episode scores:")
for _, r in episode_scores.head(5).iterrows():
    lines.append(f"  {r['episode_id']:<12} {r['show_title']:<22} score={r['combined_score']:<6} ({r['sources_used']}/3 sources)")

summary_text = "\n".join(lines)
with open("summary_report.txt", "w") as f:
    f.write(summary_text)
print(summary_text)
