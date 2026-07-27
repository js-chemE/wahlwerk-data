"""Reader for the Bundeswahlleiterin's Bundestagswahl results database.

The file is one wide table: three header rows (territory, measure, unit) over one data
row per ``Merkmal/Partei`` and election year. Turning it into wahlwerk's long form is a
pivot and nothing more -- no number in the output is computed from another.

What the source publishes as seats
----------------------------------

Three seat series sit side by side, and the difference between them is the whole reason
this module is longer than a pivot would need to be::

    Sitze einschl. Abgeordnete BE   national, including the Berlin deputies
    Sitze ohne Abgeordnete BE       national, excluding them
    Sitze                           per Land (Gesamt / Wahlkreis / Landesliste)

**Before 1990 Berlin was not part of the Wahlgebiet.** Its deputies were delegated by the
Abgeordnetenhaus under the Viermächtestatus, not elected by voters, and they held only
limited voting rights in the Bundestag. So they appear in the ``einschl.`` column, in no
Land column, and the ``ohne`` column is the result of the *election*. That is why the
Länder sum exactly to ``ohne`` in every year, and why this reader treats ``ohne`` as the
declared result: a Bundestagswahl bundle records what the Wahl produced.

A party can therefore hold seats in the ``einschl.`` column and none in ``ohne`` -- the
FDV's single seat in 1957 is exactly that, a Berlin deputy and not an elected member. Such
a party correctly contributes no row to ``declared.csv``.

2021 is the one year where reading ``ohne`` is a decision rather than a default. The
election was partially repeated in Berlin in February 2024, and the source carries that
later result in the ``einschl.`` column -- where it means something quite different from
the Berlin deputies the header names. This reader ignores that column for 2021 exactly as
it does for every other year from 1990 on, so the archive holds the Hauptwahl of
26 September 2021 and nothing else. The re-run is recorded as a note on the bundle and is
otherwise not modelled anywhere in wahlwerk.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import date
from pathlib import Path

from wahlwerk.ids import PartyId, UnitId
from wahlwerk.model import Model
from wahlwerk.registry import PartyRegistry, german_parties

from wahlwerk_data.laender import BUND, land_unit
from wahlwerk_data.parties import resolve_party

__all__ = ["ELECTION_DAY", "Election", "SeatEntry", "read_seats"]

ELECTION_DAY: dict[int, date] = {
    1949: date(1949, 8, 14),
    1953: date(1953, 9, 6),
    1957: date(1957, 9, 15),
    1961: date(1961, 9, 17),
    1965: date(1965, 9, 19),
    1969: date(1969, 9, 28),
    1972: date(1972, 11, 19),
    1976: date(1976, 10, 3),
    1980: date(1980, 10, 5),
    1983: date(1983, 3, 6),
    1987: date(1987, 1, 25),
    1990: date(1990, 12, 2),
    1994: date(1994, 10, 16),
    1998: date(1998, 9, 27),
    2002: date(2002, 9, 22),
    2005: date(2005, 9, 18),
    2009: date(2009, 9, 27),
    2013: date(2013, 9, 22),
    2017: date(2017, 9, 24),
    2021: date(2021, 9, 26),
    2025: date(2025, 2, 23),
}
"""Polling day of each Bundestagswahl. Not in the source file, which carries only the
year; the Wahlperiode is numbered by position, so 1949 is the 1st and 2025 the 21st."""

_NON_PARTY_ROWS = ("Wahlberechtigte", "Wählende", "ungültige Stimmen", "gültige Stimmen/Sitze")
"""Leading rows of the table that describe the electorate rather than a party."""

_NO_DATA = "–"  # noqa: RUF001 - an en dash is literally the character the source writes
"""En dash. The source's marker for "this did not exist / was not measured"."""


class SeatEntry(Model):
    """Seats held by one party in one unit, exactly as published."""

    unit: UnitId
    party: PartyId
    seats: int


class Election(Model):
    """One Bundestagswahl, as far as the seat distribution goes."""

    id: str
    """Bundle id: ``de.bund.2025``."""

    year: int
    date: date
    term: int
    """Which Wahlperiode this elected -- the 21st Bundestag for 2025."""

    declared: tuple[SeatEntry, ...] = ()
    """The elected result: one row per unit and party. National rows carry the unit
    ``de.bund``; the Länder carry ``de.bund.land.NN``."""

    seats_total: int = 0
    """Published national total of elected seats (``Sitze ohne Abgeordnete BE``)."""

    seats_total_incl_berlin_deputies: int | None = None
    """Elected seats plus the deputies Berlin delegated, for the elections before 1990.
    ``None`` from 1990 on, when Berlin became part of the Wahlgebiet."""


    notes: tuple[str, ...] = ()
    """Facts a reader of this bundle must know, recorded rather than resolved."""

    @property
    def national(self) -> tuple[SeatEntry, ...]:
        return tuple(e for e in self.declared if e.unit == BUND)

    @property
    def parties(self) -> tuple[PartyId, ...]:
        seen: list[PartyId] = []
        for entry in self.declared:
            if entry.party not in seen:
                seen.append(entry.party)
        return tuple(seen)


def _number(cell: str) -> int | None:
    """A cell as an integer, or ``None`` where the source records no data.

    German thousands separators are dots and the file pads with non-breaking spaces.
    Stripping those is reshaping, not computing.
    """
    text = cell.strip().replace(_NO_DATA, "").replace(".", "").replace("\xa0", "")
    return int(text) if text else None


def _header(rows: list[list[str]]) -> tuple[list[str], list[str], list[str]]:
    """Territory, measure and unit per column, with the territory forward-filled.

    The territory row is written once per group of columns and left blank afterwards,
    and long names wrap mid-cell, so both have to be repaired before the columns can be
    addressed by name.
    """
    territory: list[str] = []
    current = ""
    for cell in rows[0]:
        if cell.strip():
            current = " ".join(cell.split())
        territory.append(current)
    return territory, rows[1], rows[2]


def read_seats(path: Path, *, registry: PartyRegistry | None = None) -> tuple[Election, ...]:
    """Parse the results database into one :class:`Election` per Bundestagswahl."""
    registry = registry or german_parties()
    text = path.read_text(encoding="utf-8-sig")
    body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    rows = list(csv.reader(io.StringIO(body), delimiter=";"))
    territory, measure, unit = _header(rows)

    incl_total = _column(territory, measure, unit, "Deutschland", "Sitze einschl.", "Gesamt")
    excl_total = _column(territory, measure, unit, "Deutschland", "Sitze ohne", "Gesamt")
    land_total = {
        land_unit(territory[i]): i
        for i in range(len(measure))
        if measure[i].strip() == "Sitze" and unit[i].strip() == "Gesamt"
    }

    elections: list[Election] = []
    for index, year in enumerate(sorted(ELECTION_DAY)):
        data = [r for r in rows[3:] if r[1].strip() == str(year)]
        if not data:
            raise ValueError(f"no rows for {year} -- the source layout has changed")
        elections.append(
            _one_election(
                year=year,
                term=index + 1,
                data=data,
                registry=registry,
                incl_total=incl_total,
                excl_total=excl_total,
                land_total=land_total,
            )
        )
    return tuple(elections)


def _column(
    territory: list[str], measure: list[str], unit: list[str], where: str, what: str, how: str
) -> int:
    for i in range(len(measure)):
        if (
            territory[i] == where
            and measure[i].strip().startswith(what)
            and unit[i].strip() == how
        ):
            return i
    raise LookupError(f"no column {where}/{what}/{how} -- the source layout has changed")


def _one_election(
    *,
    year: int,
    term: int,
    data: list[list[str]],
    registry: PartyRegistry,
    incl_total: int,
    excl_total: int,
    land_total: dict[UnitId, int],
) -> Election:
    declared: list[SeatEntry] = []
    totals: dict[str, int | None] = {}
    notes: list[str] = []

    for row in data:
        label = row[0].strip()
        if label.startswith(_NON_PARTY_ROWS):
            totals["incl"] = _number(row[incl_total])
            totals["excl"] = _number(row[excl_total])
            continue

        elected = _number(row[excl_total])
        if elected is not None:
            declared.append(
                SeatEntry(unit=BUND, party=resolve_party(label, registry), seats=elected)
            )
        elif _number(row[incl_total]) is not None:
            # Seats only in the "including Berlin deputies" column: the party held a
            # delegated Berlin seat and won nothing at the ballot box. Recorded as a
            # note, never as an elected seat.
            held = _number(row[incl_total])
            seat_word = "seat" if held == 1 else "seats"
            notes.append(
                f"{label} held {held} delegated Berlin {seat_word} and won no elected "
                f"seat, so it has no row in declared.csv."
            )

        for unit_id, column in land_total.items():
            seats = _number(row[column])
            if seats is not None:
                declared.append(
                    SeatEntry(unit=unit_id, party=resolve_party(label, registry), seats=seats)
                )

    _reject_duplicates(year, declared)

    total_excl = totals.get("excl")
    total_incl = totals.get("incl")
    if total_excl is None:
        raise ValueError(f"{year}: source publishes no national seat total")

    # Only meaningful while Berlin was outside the Wahlgebiet. From 1990 the column either
    # repeats `ohne` or, in 2021, carries something else entirely -- see the module
    # docstring -- so it is read for no year after 1987.
    berlin = total_incl if year < 1990 and total_incl != total_excl else None
    return Election(
        id=f"de.bund.{year}",
        year=year,
        date=ELECTION_DAY[year],
        term=term,
        declared=tuple(declared),
        seats_total=total_excl,
        seats_total_incl_berlin_deputies=berlin,
        notes=tuple(notes) + _era_notes(year, total_excl, total_incl),
    )


def _reject_duplicates(year: int, declared: list[SeatEntry]) -> None:
    """Refuse two rows for the same party in the same unit.

    Several source labels legitimately resolve to one id -- ``B90/Gr`` and ``GRÜNE`` are
    both ``gruene`` -- and today that is safe only because the two never scored in the same
    election. If a source ever lists both with seats, the right answer is a human deciding
    whether they are one party or two, not this reader silently adding them up. Summing
    would also be computing, which a reader may not do.
    """
    counts = Counter((entry.unit, entry.party) for entry in declared)
    clashes = sorted(key for key, seen in counts.items() if seen > 1)
    if clashes:
        raise ValueError(
            f"{year}: two source labels resolve to the same party in one unit: "
            f"{clashes}. Decide whether they are one party or two -- do not sum them."
        )


def _era_notes(year: int, total_excl: int, total_incl: int | None) -> tuple[str, ...]:
    """Facts about the territory and the law that the numbers alone do not carry."""
    notes: list[str] = []
    if year < 1990 and total_incl is not None:
        notes.append(
            f"Berlin was outside the Wahlgebiet: {total_incl - total_excl} deputies were "
            f"delegated by the Abgeordnetenhaus, not elected, and held limited voting "
            f"rights. declared.csv carries the {total_excl} elected seats; the source's "
            f"'Sitze einschl. Abgeordnete BE' total of {total_incl} includes the delegates."
        )
    if year < 1952:
        notes.append(
            "The source maps results onto today's Länder: Württemberg-Baden, Baden and "
            "Württemberg-Hohenzollern appear as Baden-Württemberg, which was not formed "
            "until 1952. Preserved as published."
        )
    if year == 1949:
        notes.append("Saarland was not yet part of the Federal Republic; it joined in 1957.")
    if year == 2021:
        notes.append(
            "This is the Hauptwahl of 26 September 2021. A Wiederholungswahl was held in "
            "455 Berlin Wahlbezirke on 11 February 2024, after which the Bundestag held "
            "735 seats with the FDP on 91. That later result is not recorded here: only "
            "its national total is published, with no Land breakdown to go with it."
        )
    return tuple(notes)
