"""Aggregate the raw department CSVs into docs/summary.json.

Geotag = one report row. Output holds only district-level counts
(no names / phone numbers), safe to publish.
"""
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_FILE = ROOT / "docs" / "summary.json"

DEPARTMENTS = [
    ("forest", "Forest Department"),
    ("other_dept", "Other Departments"),
    ("coastal_habitat", "Coastal Habitat"),
    ("plant_a_tree", "Plant-a-Tree"),
    ("agriculture", "Agriculture Department"),
]

# Spellings used by other exports -> Forest Department spelling
DISTRICT_ALIASES = {
    "KALLAKURUCHI": "KALLAKURICHI",
    "SIVAGANGAI": "SIVAGANGA",
    "THIRUPATHUR": "TIRUPATTUR",
    "TIRUPATHUR": "TIRUPATTUR",
    "THOOTHUKUDI": "TUTICORIN",
    "TRICHY": "TIRUCHIRAPPALLI",
    "TIRUCHIRAPALLI": "TIRUCHIRAPPALLI",
    "NILGIRIS": "THE NILGIRIS",
    "TIRUVALLUR": "THIRUVALLUR",
    "TIRUNELVELI": "THIRUNELVELI",
    "KANNIYAKUMARI": "KANYAKUMARI",
}

IST = timezone(timedelta(hours=5, minutes=30))


def norm_district(name):
    if not isinstance(name, str) or not name.strip():
        return "UNKNOWN"
    d = re.sub(r"\s+", " ", name.strip().upper())
    return DISTRICT_ALIASES.get(d, d)


def fy_from_date(value):
    d = pd.to_datetime(value, errors="coerce")
    if pd.isna(d) or d.year < 2015:
        return "Unknown"
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{start + 1}"


def frame(district, year, seedlings):
    return pd.DataFrame({
        "district": district.map(norm_district),
        "year": year.fillna("Unknown").astype(str),
        "seedlings": pd.to_numeric(seedlings, errors="coerce").fillna(0),
    })


def load():
    read = lambda name, cols: pd.read_csv(RAW_DIR / name, usecols=cols, low_memory=False)
    parts = {}

    fo = read("forest.csv", ["District", "Division", "Year", "Seedlings"])
    parts["forest"] = frame(fo.District, fo.Year, fo.Seedlings)

    od = read("other_dept.csv", ["District", "Year", "Seedlings"])
    parts["other_dept"] = frame(od.District, od.Year, od.Seedlings)

    # Coastal Habitat has no district: map its division via Forest data
    div_to_district = (
        fo.dropna(subset=["Division", "District"])
        .groupby("Division").District.agg(lambda s: s.value_counts().index[0])
    )
    ch = read("coastal_habitat.csv", ["Division", "Year", "Seedlings"])
    parts["coastal_habitat"] = frame(ch.Division.map(div_to_district), ch.Year, ch.Seedlings)

    pt = read("plant_a_tree.csv", ["District", "Planted Date", "Number of Seedlings"])
    parts["plant_a_tree"] = frame(
        pt.District, pt["Planted Date"].map(fy_from_date), pt["Number of Seedlings"]
    )

    # Agriculture is exported one file per year (agriculture_<FY>.csv)
    agri = []
    for f in sorted(RAW_DIR.glob("agriculture_*.csv")):
        a = pd.read_csv(f, usecols=["District", "Number of Seedlings"], low_memory=False)
        fy = f.stem.split("_", 1)[1]
        agri.append(frame(a.District, pd.Series(fy, index=a.index), a["Number of Seedlings"]))
    parts["agriculture"] = pd.concat(agri) if agri else frame(*(pd.Series(dtype=str),) * 3)

    return parts


def build():
    parts = load()
    rows = []
    for key, _ in DEPARTMENTS:
        g = parts[key].groupby(["district", "year"]).agg(
            geotags=("seedlings", "size"), seedlings=("seedlings", "sum")
        )
        for (district, year), r in g.iterrows():
            rows.append([district, key, year, int(r.geotags), int(r.seedlings)])

    rows.sort()
    updated = datetime.now(IST).isoformat(timespec="seconds")
    # Keep the old timestamp when nothing changed, so "Data updated" means real changes
    if OUT_FILE.exists():
        old = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        if old.get("rows") == rows:
            updated = old["updated"]

    summary = {
        "updated": updated,
        "departments": [{"key": k, "label": l} for k, l in DEPARTMENTS],
        "years": sorted({r[2] for r in rows}),
        "districts": sorted({r[0] for r in rows}),
        "columns": ["district", "department", "year", "geotags", "seedlings"],
        "rows": rows,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(summary, separators=(",", ":")), encoding="utf-8")

    for key, label in DEPARTMENTS:
        print(f"  {label}: {sum(r[3] for r in rows if r[1] == key):,} geotags")
    return summary


if __name__ == "__main__":
    build()
