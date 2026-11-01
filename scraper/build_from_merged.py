"""Aggregate the merged gtm-data export into docs/summary.json.

Geotag = one report row. Output holds only district-level counts
(no names / phone numbers), safe to publish. Stops without writing
if the file looks wrong, so bad data never reaches the live page.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_summary import DEPARTMENTS, IST, OUT_FILE, frame  # noqa: E402

# Department name in the merged file -> dashboard department key
DEPARTMENT_KEYS = {
    "Forest Department": "forest",
    "Other Department": "other_dept",
    "Coastal Department": "coastal_habitat",
    "Plant-a-Tree": "plant_a_tree",
    "Agriculture Department": "agriculture",
}
COLUMNS = ["Department", "District", "Division", "Year", "Seedlings", "Number of Seedlings"]
# Refuse a file with far fewer rows than the page already shows
MIN_ROW_RATIO = 0.9


class BadData(Exception):
    pass


def load(path):
    df = pd.read_csv(path, usecols=COLUMNS, dtype=str, low_memory=False)
    df["Department"] = df["Department"].str.strip()

    found = set(df["Department"].dropna())
    if found != set(DEPARTMENT_KEYS) or df["Department"].isna().any():
        raise BadData(f"Unexpected or blank departments: {sorted(found)}")

    # Coastal Habitat has no district: map its division via Forest data
    forest = df[df["Department"] == "Forest Department"]
    div_to_district = (
        forest.dropna(subset=["Division", "District"])
        .groupby("Division").District.agg(lambda s: s.value_counts().index[0])
    )
    coastal = df["Department"] == "Coastal Department"
    df.loc[coastal, "District"] = df.loc[coastal, "Division"].map(div_to_district)

    seedlings = df["Seedlings"].fillna(df["Number of Seedlings"])
    parts = frame(df["District"], df["Year"], seedlings)
    parts["department"] = df["Department"].map(DEPARTMENT_KEYS)
    return parts


def build(path, updated, out_file=OUT_FILE):
    parts = load(path)
    old = json.loads(out_file.read_text(encoding="utf-8")) if out_file.exists() else None

    if old:
        new_districts = set(parts["district"]) - set(old["districts"]) - {"UNKNOWN"}
        if new_districts:
            raise BadData(f"Unrecognised districts: {sorted(new_districts)}")
        old_total = sum(r[3] for r in old["rows"])
        if len(parts) < old_total * MIN_ROW_RATIO:
            raise BadData(f"Only {len(parts):,} rows, page already shows {old_total:,}")

    g = parts.groupby(["district", "department", "year"]).agg(
        geotags=("seedlings", "size"), seedlings=("seedlings", "sum")
    )
    rows = sorted(
        [district, key, year, int(r.geotags), int(r.seedlings)]
        for (district, key, year), r in g.iterrows()
    )
    # Every row in the file must be counted on the page
    if sum(r[3] for r in rows) != len(parts):
        raise BadData(f"Counted {sum(r[3] for r in rows):,} of {len(parts):,} rows")

    summary = {
        "updated": datetime.fromisoformat(updated.replace("Z", "+00:00")).astimezone(IST).isoformat(timespec="seconds"),
        "departments": [{"key": k, "label": l} for k, l in DEPARTMENTS],
        "years": sorted({r[2] for r in rows}),
        "districts": sorted({r[0] for r in rows}),
        "columns": ["district", "department", "year", "geotags", "seedlings"],
        "rows": rows,
    }
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(summary, separators=(",", ":")), encoding="utf-8")

    for key, label in DEPARTMENTS:
        print(f"  {label}: {sum(r[3] for r in rows if r[1] == key):,} geotags")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("merged", type=Path, help="path to merged.csv.gz")
    parser.add_argument("updated", help="the file's upload time (ISO 8601)")
    parser.add_argument("--out", type=Path, default=OUT_FILE)
    args = parser.parse_args()
    try:
        build(args.merged, args.updated, args.out)
    except BadData as err:
        sys.exit(f"Not publishing: {err}")
