"""Offline place names (GeoNames cities >= 15k inhabitants plus countries, CC BY 4.0).

Used to suggest coordinates for place-name tags, to search places when setting a location by
hand and to describe GPS positions ("near Rome"). Nothing is sent over the network. The data
file is built by ``scripts/build_gazetteer.py`` and loaded lazily on first use.
"""

import bisect
import csv
import gzip
import math
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).with_name("data") / "places.tsv.gz"
ATTRIBUTION = "Place names © GeoNames (CC BY 4.0)"
# Nearest-place lookups bucket places into 1 by 1 degree cells.
_CELL_DEG = 1.0
NEAR_MAX_KM = 50.0


@dataclass(frozen=True)
class Place:
    kind: str  # "city" | "country"
    name: str
    admin1: str
    country_code: str
    country: str
    latitude: float
    longitude: float
    population: int

    @property
    def label(self) -> str:
        if self.kind == "country":
            return self.name
        parts = [self.name]
        if self.admin1 and name_key(self.admin1) != name_key(self.name):
            parts.append(self.admin1)
        parts.append(self.country)
        return ", ".join(parts)


def name_key(text: str) -> str:
    """Case-, accent- and whitespace-insensitive key ("São  Paulo" -> "sao paulo")."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.casefold().replace("-", " ").split())


@dataclass(frozen=True)
class _Index:
    places: tuple[Place, ...]
    by_key: dict[str, tuple[int, ...]]
    sorted_keys: tuple[str, ...]
    sorted_ids: tuple[int, ...]
    cells: dict[tuple[int, int], tuple[int, ...]]


def _rank(place: Place) -> tuple[int, int]:
    return (0 if place.kind == "country" else 1, -place.population)


@lru_cache(maxsize=1)
def _index() -> _Index:
    places: list[Place] = []
    names: list[list[str]] = []
    with gzip.open(DATA_FILE, "rt", encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            kind, name, admin1, cc, country, lat, lon, pop, alts = row
            places.append(Place(kind, name, admin1, cc, country, float(lat), float(lon), int(pop)))
            names.append([name, *filter(None, alts.split("|"))])

    by_key: dict[str, list[int]] = {}
    for i, place_names in enumerate(names):
        for key in dict.fromkeys(name_key(n) for n in place_names):
            by_key.setdefault(key, []).append(i)
    ordered = {k: tuple(sorted(ids, key=lambda i: _rank(places[i]))) for k, ids in by_key.items()}
    pairs = sorted((k, i) for k, ids in ordered.items() for i in ids)

    cells: dict[tuple[int, int], list[int]] = {}
    for i, p in enumerate(places):
        if p.kind == "city":
            cells.setdefault(_cell(p.latitude, p.longitude), []).append(i)
    return _Index(
        places=tuple(places),
        by_key=ordered,
        sorted_keys=tuple(k for k, _ in pairs),
        sorted_ids=tuple(i for _, i in pairs),
        cells={c: tuple(ids) for c, ids in cells.items()},
    )


def _cell(lat: float, lon: float) -> tuple[int, int]:
    return math.floor(lat / _CELL_DEG), math.floor(lon / _CELL_DEG)


def lookup(name: str, limit: int = 5) -> list[Place]:
    """Places whose name (or a local/alternative spelling) is exactly ``name``, best first."""
    index = _index()
    return [index.places[i] for i in index.by_key.get(name_key(name), ())[:limit]]


def search(text: str, limit: int = 10) -> list[Place]:
    """Places whose name starts with ``text``: exact matches first, then by size."""
    key = name_key(text)
    if len(key) < 2:
        return []
    index = _index()
    start = bisect.bisect_left(index.sorted_keys, key)
    found: dict[int, bool] = {}
    for pos in range(start, len(index.sorted_keys)):
        if not index.sorted_keys[pos].startswith(key) or len(found) >= 500:
            break
        place_id = index.sorted_ids[pos]
        found[place_id] = found.get(place_id, False) or index.sorted_keys[pos] == key

    def order(i: int) -> tuple[bool, bool, int, int]:
        primary = name_key(index.places[i].name).startswith(key)
        return (not found[i], not primary, *_rank(index.places[i]))

    return [index.places[i] for i in sorted(found, key=order)[:limit]]


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(a)))


def nearest(latitude: float, longitude: float, max_km: float = NEAR_MAX_KM) -> Place | None:
    """The closest listed town within ``max_km`` (larger towns win near-ties)."""
    index = _index()
    row, col = _cell(latitude, longitude)
    best: tuple[float, Place] | None = None
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            for i in index.cells.get((row + dr, col + dc), ()):
                place = index.places[i]
                km = distance_km(latitude, longitude, place.latitude, place.longitude)
                # Bigger places win near-ties (a city of 1M by ~2 km over a 15k town).
                score = km - min(5.0, math.log10(max(place.population, 1)) - 4)
                if km <= max_km and (best is None or score < best[0]):
                    best = (score, place)
    return best[1] if best else None
