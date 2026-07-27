"""Integrity tests over the committed archive.

These read the bundles as a consumer would -- no ingestion code involved -- so they fail
if a bundle is hand-edited into an inconsistent state, not only if the reader regresses.

The seat totals below are the independent check. They are not taken from the source file
the bundles were built from; they are the figures in the historical record, so a reader
bug that shifted every row by one column would show up here rather than agreeing with
itself.
"""

from __future__ import annotations

import csv
import tomllib
from pathlib import Path

import pytest
from wahlwerk.registry import german_parties

ARCHIVE = Path(__file__).resolve().parents[1] / "elections"

YEARS = (
    1949, 1953, 1957, 1961, 1965, 1969, 1972, 1976, 1980, 1983, 1987,
    1990, 1994, 1998, 2002, 2005, 2009, 2013, 2017, 2021, 2025,
)  # fmt: skip

KNOWN_TOTALS = {
    1949: 402,  # plus 8 delegated Berlin deputies
    1953: 487,  # plus 22, and so on to 1987
    1957: 497,
    1987: 497,
    1990: 662,  # first all-German Bundestag
    2013: 631,
    2017: 709,
    2021: 736,  # Hauptwahl; 735 after the Wiederholungswahl of 11 February 2024
    2025: 630,  # the first election under BWahlG 2023
}

BUNDESTAG_2025 = {
    "cdu": 164, "afd": 152, "spd": 120, "gruene": 85, "linke": 64, "csu": 44, "ssw": 1,
}  # fmt: skip


def bundle(year: int) -> Path:
    """``de.bund.2025`` lives at ``elections/de.bund/2025`` -- id split on its last dot."""
    return ARCHIVE / "de.bund" / str(year)


def manifest(year: int) -> dict[str, object]:
    with (bundle(year) / "election.toml").open("rb") as handle:
        return tomllib.load(handle)


def declared(year: int) -> list[dict[str, str]]:
    text = (bundle(year) / "declared.csv").read_text(encoding="utf-8")
    return list(csv.DictReader(text.splitlines()))


def national(year: int) -> dict[str, int]:
    return {r["party"]: int(r["seats"]) for r in declared(year) if r["unit"] == "de.bund"}


def test_every_bundestagswahl_since_1949_is_present() -> None:
    assert sorted(p.name for p in ARCHIVE.iterdir() if p.is_dir()) == ["de.bund"]
    assert sorted(p.name for p in (ARCHIVE / "de.bund").iterdir() if p.is_dir()) == [
        str(y) for y in YEARS
    ]


@pytest.mark.parametrize("year", YEARS)
def test_manifest_declares_schema_and_body(year: int) -> None:
    meta = manifest(year)
    assert meta["schema"] == 1
    assert meta["id"] == f"de.bund.{year}"
    assert meta["body"] == "de.bund.bundestag"
    assert meta["term"] == YEARS.index(year) + 1


@pytest.mark.parametrize("year", YEARS)
def test_parties_sum_to_the_declared_total(year: int) -> None:
    assert sum(national(year).values()) == manifest(year)["seats_total"]


@pytest.mark.parametrize("year", YEARS)
def test_laender_sum_to_the_declared_total(year: int) -> None:
    """Every elected seat belongs to exactly one Land, in every era."""
    laender = sum(int(r["seats"]) for r in declared(year) if r["unit"] != "de.bund")
    assert laender == manifest(year)["seats_total"]


@pytest.mark.parametrize("year", YEARS)
def test_each_party_national_total_matches_its_laender(year: int) -> None:
    rows = declared(year)
    for party, seats in national(year).items():
        across = sum(
            int(r["seats"]) for r in rows if r["unit"] != "de.bund" and r["party"] == party
        )
        assert across == seats, f"{party} in {year}"


@pytest.mark.parametrize(("year", "total"), sorted(KNOWN_TOTALS.items()))
def test_totals_match_the_historical_record(year: int, total: int) -> None:
    assert manifest(year)["seats_total"] == total


def test_2025_reproduces_the_reference_chamber() -> None:
    """The 21st Bundestag, party by party, against wahlwerk's own reference chamber."""
    assert national(2025) == BUNDESTAG_2025


def test_2021_is_the_hauptwahl_and_carries_no_rerun_field() -> None:
    """The Wiederholungswahl is a note and nothing else -- no field, no second variant.

    The source offers a 735-seat figure for 2021 in the column that elsewhere counts Berlin
    deputies. Reading it would mean carrying two results for one election, so the archive
    ignores it and keeps the Hauptwahl, which is also the only variant with a Land
    breakdown.
    """
    meta = manifest(2021)
    assert meta["seats_total"] == 736
    assert national(2021)["fdp"] == 92, "declared.csv is the Hauptwahl, where FDP had 92"
    assert "seats_total_after_wiederholungswahl" not in meta
    assert "seats_total_incl_berlin_deputies" not in meta
    assert any("Wiederholungswahl" in note for note in notes(2021))


@pytest.mark.parametrize("year", [y for y in YEARS if y < 1990])
def test_delegated_berlin_deputies_are_recorded_but_not_declared(year: int) -> None:
    """Berlin's deputies were delegated by the Abgeordnetenhaus, never elected."""
    meta = manifest(year)
    extra = meta["seats_total_incl_berlin_deputies"]
    assert isinstance(extra, int)
    assert extra > int(meta["seats_total"])  # type: ignore[call-overload]
    assert "de.bund.land.11" not in {r["unit"] for r in declared(year)}


@pytest.mark.parametrize("year", [y for y in YEARS if y >= 1990])
def test_no_berlin_deputy_field_once_berlin_votes(year: int) -> None:
    assert "seats_total_incl_berlin_deputies" not in manifest(year)


@pytest.mark.parametrize("year", YEARS)
def test_every_party_is_resolvable(year: int) -> None:
    """No bundle may name a party the registry does not know.

    This is the phantom-party guard: an id that resolves nowhere is exactly the silent
    failure the registry exists to prevent. The registry is the single namespace authority
    -- a bundle never mints an id of its own, so there is nowhere else to look.
    """
    registry = german_parties()
    for party in national(year):
        assert party in registry, f"{party} in {year} is in no registry"


@pytest.mark.parametrize("year", YEARS)
def test_manifest_carries_attribution(year: int) -> None:
    """dl-de/by-2-0 requires it; a bundle without it may not be redistributed."""
    source = manifest(year)["source"]
    assert isinstance(source, dict)
    assert source["licence"] == "dl-de/by-2-0"
    assert source["attribution"]
    assert len(source["sha256"]) == 64


@pytest.mark.parametrize("year", YEARS)
def test_contents_lists_exactly_the_files_present(year: int) -> None:
    """An absent file means "not ingested", so the manifest must not overstate."""
    listed = set(manifest(year)["contents"])  # type: ignore[call-overload]
    actual = {p.name for p in bundle(year).iterdir() if p.name != "election.toml"}
    assert listed == actual


@pytest.mark.parametrize("year", YEARS)
def test_notes_are_top_level_and_not_swallowed_by_the_source_table(year: int) -> None:
    """In TOML every key after a table header belongs to that table.

    Emitting `notes` after `[source]` filed them under `source.notes`, where no reader
    looks — the manifest parsed, so nothing complained, and the caveats about Berlin and
    the 2021 Wiederholungswahl were silently invisible.
    """
    data = manifest(year)
    source = data["source"]
    assert isinstance(source, dict)
    assert "notes" not in source, "notes fell inside [source] — emit them before it"


def notes(year: int) -> list[str]:
    found = manifest(year).get("notes", [])
    assert isinstance(found, list)
    return [str(n) for n in found]


def test_the_elections_with_caveats_carry_them() -> None:
    for year in (1949, 1953, 1987):
        assert any("Berlin" in n for n in notes(year))
    assert any("Wiederholungswahl" in n for n in notes(2021))


@pytest.mark.parametrize("year", YEARS)
def test_the_engine_can_build_a_chamber_from_every_bundle(year: int) -> None:
    """The consumer's view: `Chamber.from_archive` is why this archive exists."""
    from wahlwerk.state import Chamber

    chamber = Chamber.from_archive(f"de.bund.{year}", root=ARCHIVE.parent)
    assert chamber.size == manifest(year)["seats_total"]
    assert chamber.seats_by_party == national(year)
    assert chamber.term.elected_on is not None
    assert chamber.term.start is None, "no bundle records the constitutive session"


def test_the_2025_chamber_matches_the_reference_chamber_in_the_engine() -> None:
    """Two independent paths to the same 630 seats: typed in, and read from the archive."""
    from wahlwerk.examples.bundestag_2025 import build
    from wahlwerk.state import Chamber

    from_archive = Chamber.from_archive("de.bund.2025", root=ARCHIVE.parent)
    assert from_archive.seats_by_party == build().seats_by_party


def test_reader_refuses_two_labels_resolving_to_one_party() -> None:
    """Folding B90/Gr into gruene is safe only while the two never score together.

    It holds for 1949-2025 because DIE GRÜNEN won nothing in 1990, the one year both
    lists stood. If a future source lists both with seats, the reader must stop rather
    than quietly add them up.
    """
    from wahlwerk.ids import PartyId, UnitId

    from wahlwerk_data.bundeswahlleiterin import SeatEntry, _reject_duplicates

    rows = [
        SeatEntry(unit=UnitId("de.bund"), party=PartyId("gruene"), seats=8),
        SeatEntry(unit=UnitId("de.bund"), party=PartyId("gruene"), seats=3),
    ]
    with pytest.raises(ValueError, match="same party in one unit"):
        _reject_duplicates(1990, rows)

    _reject_duplicates(1990, rows[:1])  # one row per party is fine
