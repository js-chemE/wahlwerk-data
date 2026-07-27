"""Official sources: where a file came from, and proof that it has not changed.

A bundle is only as trustworthy as the provenance recorded beside it, so every source
carries the URL it was fetched from, the licence it is published under and the SHA-256 of
the exact bytes a bundle was built from. dl-de/by-2-0 additionally *requires*
attribution, so ``attribution`` is not optional decoration -- it is the licence condition.

Raw downloads are cached outside the repository. The multi-megabyte original is not the
archive's job to keep: the bundle plus the recorded checksum is what makes the result
reproducible.
"""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

from wahlwerk.model import Model

__all__ = ["BTW_AB49", "Source", "cache_dir", "fetch"]


class Source(Model):
    """One published file, and the terms it comes with."""

    key: str
    """Short stable name, used as the cache filename: ``btw_ab49``."""

    title: str
    """The publisher's own title for the dataset, in German, verbatim."""

    url: str

    publisher: str
    attribution: str
    """The credit line the licence requires be reproduced. Not optional."""

    licence: str = "dl-de/by-2-0"
    licence_url: str = "https://www.govdata.de/dl-de/by-2-0"

    landing_page: str = ""
    """Human-facing page the file is linked from, for a reader who wants context."""


BTW_AB49 = Source(
    key="btw_ab49",
    title=(
        "Wahlberechtigte, Wählende, Stimmabgabe und Sitzverteilung bei den "
        "Bundestagswahlen seit 1949 nach Ländern"
    ),
    url=(
        "https://www.bundeswahlleiterin.de/dam/jcr/"
        "24d8e745-920d-431a-893a-12805bc7ef40/btw_ab49_datenbank_ergebnisse.csv"
    ),
    publisher="Die Bundeswahlleiterin, Statistisches Bundesamt (Destatis)",
    attribution="© Die Bundeswahlleiterin, Statistisches Bundesamt (Destatis), 2026",
    landing_page="https://www.bundeswahlleiterin.de/bundestagswahlen/1949.html",
)
"""The Bundeswahlleiterin's own results database: every Bundestagswahl since 1949 in one
file, per Land, including the Sitzverteilung.

This supersedes scraping the twenty-one per-election pages. It is the same publisher, it
is machine-readable rather than parsed out of HTML tables, and it is internally
consistent in a way the pages cannot be checked for: the Länder sum exactly to the
published national total in all twenty-one elections.
"""


def cache_dir() -> Path:
    """Where raw downloads live -- outside the repository, never committed."""
    return Path.home() / ".cache" / "wahlwerk-data"


def fetch(source: Source, *, refresh: bool = False) -> tuple[Path, str]:
    """Download a source if it is not already cached; return its path and SHA-256.

    The checksum is of the bytes on disk, computed on every call rather than trusted
    from a previous run, so a corrupted or hand-edited cache cannot quietly produce a
    bundle that claims a provenance it does not have.
    """
    target = cache_dir() / f"{source.key}.csv"
    if refresh or not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(source.url) as response:
            target.write_bytes(response.read())
    return target, hashlib.sha256(target.read_bytes()).hexdigest()
