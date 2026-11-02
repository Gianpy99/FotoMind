"""Build the offline place list used to resolve place-name tags (no network at runtime).

Source: GeoNames (https://www.geonames.org), CC BY 4.0. Downloads cities15000.zip,
admin1CodesASCII.txt and countryInfo.txt into a cache folder and writes
backend/fotomind/modules/places/data/places.tsv.gz with one row per place:

    kind  name  admin1  country_code  country  latitude  longitude  population  alt_names

``kind`` is ``city`` or ``country``; ``alt_names`` is ``|``-separated (Latin script only, so
local spellings such as "Roma" or "Firenze" are kept). Country positions are the
population-weighted centre of their cities.

    python scripts/build_gazetteer.py [--cache DIR]
"""

import argparse
import csv
import gzip
import io
import tempfile
import unicodedata
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

BASE = "https://download.geonames.org/export/dump/"
OUT = Path(__file__).resolve().parents[1] / "backend/fotomind/modules/places/data/places.tsv.gz"
MAX_ALT_NAMES = 40


def fetch(cache: Path, name: str) -> Path:
    path = cache / name
    if not path.exists():
        print(f"downloading {name}")
        urllib.request.urlretrieve(BASE + name, path)
    return path


def latin(name: str) -> bool:
    for ch in name:
        if ch.isalpha() and not unicodedata.name(ch, "").startswith("LATIN"):
            return False
    return True


def useful_alt(name: str, primary: str) -> bool:
    if len(name) < 3 or name.casefold() == primary.casefold() or not latin(name):
        return False
    # Lower-case entries are machine romanisations of non-Latin names ("luo ma").
    if not name[0].isupper():
        return False
    # Skip airport/station codes such as "FCO" or "ROM".
    return not (name.isupper() and len(name) <= 4) and not any(c.isdigit() for c in name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, default=Path(tempfile.gettempdir()) / "geonames")
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)

    countries: dict[str, str] = {}
    for line in fetch(args.cache, "countryInfo.txt").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            cols = line.split("\t")
            countries[cols[0]] = cols[4]

    admin1: dict[str, str] = {}
    text = fetch(args.cache, "admin1CodesASCII.txt").read_text(encoding="utf-8")
    for line in text.splitlines():
        cols = line.split("\t")
        if len(cols) >= 2:
            admin1[cols[0]] = cols[1]

    rows: list[list[str]] = []
    weight: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    with zipfile.ZipFile(fetch(args.cache, "cities15000.zip")) as zf:
        raw = zf.read("cities15000.txt").decode("utf-8")
    for line in raw.splitlines():
        cols = line.split("\t")
        name, alts, lat, lon, cc, a1, pop = (
            cols[1], cols[3], float(cols[4]), float(cols[5]), cols[8], cols[10], int(cols[14] or 0)
        )  # fmt: skip
        if cc not in countries:
            continue
        alt_names = list(dict.fromkeys(a for a in alts.split(",") if useful_alt(a, name)))
        rows.append(
            [
                "city",
                name,
                admin1.get(f"{cc}.{a1}", ""),
                cc,
                countries[cc],
                f"{lat:.4f}",
                f"{lon:.4f}",
                str(pop),
                "|".join(alt_names[:MAX_ALT_NAMES]),
            ]
        )
        w = weight[cc]
        w[0] += lat * pop
        w[1] += lon * pop
        w[2] += pop
        w[3] += 1
    for cc, (lat_sum, lon_sum, pop_sum, _n) in weight.items():
        if pop_sum <= 0:
            continue
        rows.append(
            [
                "country",
                countries[cc],
                "",
                cc,
                countries[cc],
                f"{lat_sum / pop_sum:.4f}",
                f"{lon_sum / pop_sum:.4f}",
                str(int(pop_sum)),
                "",
            ]
        )

    rows.sort(key=lambda r: (r[0] != "country", -int(r[7])))
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_NONE)
    writer.writerows(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0 keeps the output byte-identical between runs.
    with gzip.GzipFile(OUT, "wb", mtime=0) as gz:
        gz.write(buf.getvalue().encode("utf-8"))
    print(f"wrote {len(rows)} places to {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
