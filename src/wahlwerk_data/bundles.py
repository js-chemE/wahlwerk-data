"""Writing a bundle: one directory per election, plain CSV plus provenance.

An election id maps to a path by splitting on its last dot: ``de.bund.2025`` lives at
``elections/de.bund/2025``. Everything before that dot is the jurisdiction and becomes the
directory, so an archive stays navigable as it grows -- ``de.by/2023``,
``de.nw.koeln/2025`` -- instead of flattening every level of government into one listing.

Only the files an election actually has data for are written. A seat-distribution bundle
carries ``declared.csv`` and no ``tally.csv``, and says so in ``election.toml`` through
``contents``. An absent file means the data has not been ingested, never that the election
had no votes -- which is why the manifest lists what is present rather than leaving a
reader to infer it from a directory listing.

CSV is written with ``\\n`` endings and a trailing newline so that a bundle produced on
Windows and one produced on Linux are byte-identical, and a diff shows a changed number
rather than a changed line ending.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from wahlwerk_data.bundeswahlleiterin import Election
from wahlwerk_data.laender import BUND
from wahlwerk_data.sources import Source

__all__ = ["SCHEMA", "bundle_path", "write_bundle"]

SCHEMA = 1
"""Bundle format version, written into every ``election.toml``. The engine declares the
range it reads, so a format change breaks loudly instead of mis-parsing quietly."""

_LAW = {
    # Which BWahlG version governed each election. Only the versions wahlwerk names in
    # its build order are asserted here; the rest are left out rather than guessed.
    2025: "de.bund.bwahlg.2023",
    2021: "de.bund.bwahlg.2013",
}


def bundle_path(root: Path, election_id: str) -> Path:
    """``de.bund.2025`` -> ``<root>/de.bund/2025``.

    The last segment of the id is the election; everything before it is the jurisdiction
    and becomes the directory. Readers use this too, so the mapping is defined once.
    """
    jurisdiction, _, election = election_id.rpartition(".")
    if not jurisdiction:
        raise ValueError(f"election id {election_id!r} needs a jurisdiction and an election")
    return root / jurisdiction / election


def _csv(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def _toml_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _manifest(election: Election, source: Source, digest: str, contents: list[str]) -> str:
    lines = [
        f"schema = {SCHEMA}",
        f'id = "{election.id}"',
        'body = "de.bund.bundestag"',
        f"date = {election.date.isoformat()}",
        f"term = {election.term}",
        f"seats_total = {election.seats_total}",
    ]
    if election.seats_total_incl_berlin_deputies is not None:
        lines.append(
            f"seats_total_incl_berlin_deputies = {election.seats_total_incl_berlin_deputies}"
        )
    law = _LAW.get(election.year)
    if law:
        lines.append(f'law = "{law}"')
    lines += [
        "",
        "contents = [" + ", ".join(f'"{c}"' for c in contents) + "]",
    ]
    # Notes must precede [source]: in TOML every key after a table header belongs to that
    # table, so emitting them afterwards silently files them under source.notes.
    if election.notes:
        lines += ["", "notes = ["]
        lines += [f'  "{_toml_escape(note)}",' for note in election.notes]
        lines += ["]"]
    lines += [
        "",
        "[source]",
        f'publisher = "{_toml_escape(source.publisher)}"',
        f'title = "{_toml_escape(source.title)}"',
        f'url = "{source.url}"',
        f'landing_page = "{source.landing_page}"',
        f'licence = "{source.licence}"',
        f'licence_url = "{source.licence_url}"',
        f'attribution = "{_toml_escape(source.attribution)}"',
        f'sha256 = "{digest}"',
        f"retrieved = {_RETRIEVED}",
    ]
    return "\n".join(lines) + "\n"


_RETRIEVED = "2026-07-27"


def write_bundle(election: Election, root: Path, source: Source, digest: str) -> Path:
    """Write one election's bundle under ``root``; return the directory."""
    directory = bundle_path(root, election.id)
    directory.mkdir(parents=True, exist_ok=True)

    declared = sorted(
        election.declared,
        # National rows first, then Länder in official key order, parties alphabetical
        # within a unit -- a stable order so a re-ingest produces a zero-line diff.
        key=lambda e: ("" if e.unit == BUND else e.unit, e.party),
    )
    (directory / "declared.csv").write_text(
        _csv(
            ("unit", "party", "seats"),
            [(e.unit, e.party, str(e.seats)) for e in declared],
        ),
        encoding="utf-8",
    )
    contents = ["declared.csv"]

    (directory / "election.toml").write_text(
        _manifest(election, source, digest, contents), encoding="utf-8"
    )
    return directory
