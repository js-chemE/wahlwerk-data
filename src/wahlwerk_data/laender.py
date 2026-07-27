"""The sixteen Länder as wahlwerk ``UnitId``s, keyed by the name sources spell out.

The numbers are the official Land keys used by Destatis and the Bundeswahlleiterin (the
first two digits of the Amtlicher Gemeindeschlüssel), not an ordering invented here.
They are what the source files are organised by, so using anything else would mean
translating a key that already exists.

Two historical wrinkles the caller has to know about, because they are properties of the
territory rather than of this mapping:

* **Saarland** only joined the Federal Republic on 1 January 1957, so it first appears
  in the Bundestagswahl of 1957.
* **Berlin** was not part of the Wahlgebiet before 1990. Its deputies were delegated by
  the Abgeordnetenhaus rather than elected, which is why the Bundeswahlleiterin carries
  them in a separate national column and in no Land column at all. See
  :mod:`wahlwerk_data.bundeswahlleiterin`.

Pre-1952 results are published against the modern Länder: the Bundeswahlleiterin maps
Württemberg-Baden, Baden and Württemberg-Hohenzollern onto Baden-Württemberg, which did
not exist until 1952. That is the source's choice and it is preserved rather than undone,
but it is recorded in the affected bundles' ``election.toml``.
"""

from __future__ import annotations

import re

from wahlwerk.ids import UnitId

__all__ = ["BUND", "LAND_BY_NAME", "land_unit"]

BUND = UnitId("de.bund")
"""The federal territory as a whole -- the unit a national seat total belongs to."""

_LAND_KEY: dict[str, int] = {
    "Schleswig-Holstein": 1,
    "Hamburg": 2,
    "Niedersachsen": 3,
    "Bremen": 4,
    "Nordrhein-Westfalen": 5,
    "Hessen": 6,
    "Rheinland-Pfalz": 7,
    "Baden-Württemberg": 8,
    "Bayern": 9,
    "Saarland": 10,
    "Berlin": 11,
    "Brandenburg": 12,
    "Mecklenburg-Vorpommern": 13,
    "Sachsen": 14,
    "Sachsen-Anhalt": 15,
    "Thüringen": 16,
}

LAND_BY_NAME: dict[str, UnitId] = {
    name: UnitId(f"de.bund.land.{key:02d}") for name, key in _LAND_KEY.items()
}
"""Official Land name as sources spell it, to the wahlwerk unit id."""

LAND_NAME: dict[UnitId, str] = {unit: name for name, unit in LAND_BY_NAME.items()}
"""The inverse, for writing a human-readable name into a bundle."""


def land_unit(name: str) -> UnitId:
    """Resolve a Land name to its unit id.

    Whitespace is normalised because the source's column headers wrap mid-name, and they
    wrap *after the hyphen* -- ``"Mecklenburg-\\nVorpommern"`` -- so the line break has to
    be closed up rather than turned into a space. No German Land name contains a space, so
    this cannot merge two words that belong apart.

    Nothing else is normalised: an unrecognised spelling raises rather than being guessed
    at, exactly as party resolution does.
    """
    cleaned = re.sub(r"-\s+", "-", " ".join(name.split()))
    try:
        return LAND_BY_NAME[cleaned]
    except KeyError:
        raise LookupError(f"no Land named {cleaned!r} -- add it to laender.py") from None
