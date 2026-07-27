# wahlwerk-data

The archive: normalised German election data for the [wahlwerk](https://github.com/js-chemE/wahlwerk)
engine. One directory per election, plain CSV, plus the ingestion code that produces it.
Published under Datenlizenz Deutschland (dl-de/by-2-0); the engine is Apache-2.0, which is
why these are two repositories.

**Status: seat distributions for all 21 Bundestagswahlen, 1949–2025.** Every bundle carries
`declared.csv` — the official Sitzverteilung, nationally and per Land, 1 239 rows and 16
parties in total. No vote data yet: no `tally.csv`, no `units.csv`, no `candidacies.csv`.
Each `election.toml` lists what it actually has in `contents`, so an absent file always
means "not ingested" and never "this election had none".

## Commands

```bash
uv sync
uv run wahlwerk-ingest             # fetch if needed, cross-check, write elections/
uv run wahlwerk-ingest --refresh   # re-download the source first
uv run wahlwerk-ingest --check     # verify only, write nothing
uv run wahlwerk-ingest --root DIR  # write somewhere other than elections/
uv run pytest -q                   # 225 tests over the committed bundles
uv run mypy                        # strict; src and tests
uv run ruff check . && uv run ruff format .
```

All of them must pass before anything is called done.

`--check` parses the source and runs the cross-checks without writing, so it answers "does
the upstream file still hold together?". It does **not** compare against the committed
bundles — `pytest` is what guards those. Run both.

This repo depends on `wahlwerk` through an editable path dependency
(`[tool.uv.sources]`), so `uv sync` needs the sibling clone at `../wahlwerk`.

## The one rule everything else follows from

> **Readers reshape. They never compute.**

Rename, pivot, strip a thousands separator, resolve a label to an id — all reshaping. But
if the source publishes a percentage, store the count. If it publishes seat totals, those
go in `declared.csv` and never into a tally. **Any arithmetic in a reader is a bug.**

Deriving seats from votes is the *engine's* job, and `declared.csv` is the independent
check on whether it got them right. A reader that computes a seat total has destroyed the
only thing that could have caught the engine being wrong — and it will agree with itself
forever while doing it.

The one arithmetic in `cli.py` is not an exception: `_check` compares two figures that both
come from the source, which is a consistency test, not a derivation.

## Hard rules

- **A bundle never mints a party id.** `wahlwerk`'s registry is the single namespace
  authority. `resolve_party` normalises nothing beyond what the registry does and has **no
  fuzzy fallback**: an unrecognised spelling raises and is a data question for a human. A
  quietly-invented party is exactly how a phantom with seats and no votes appears. Adding
  one means two rows in the engine's `data/parties_de.csv` and `data/party_aliases_de.csv`,
  with a verified long name — never a guess.
- **Two rows for one party in one unit is an error, never a sum.** Several source labels
  legitimately resolve to one id — `B90/Gr` and `GRÜNE` are both `gruene` — and that fold
  is safe only because the two never scored in the same election. `_reject_duplicates`
  raises if they ever do. Adding them up would be computing, which a reader may not do, and
  whether they are one party or two is a human's call.
- **Record absence, never invent it.** A party that held only a delegated Berlin seat gets
  a `notes` entry and **no** row in `declared.csv`. A Land that did not exist yet gets no
  rows. Never interpolate, never zero-fill.
- **Raw dumps are not committed.** `election.toml` records URL, retrieval date and SHA-256;
  that is what makes a bundle reproducible. The download is cached in
  `~/.cache/wahlwerk-data/`, and the checksum is recomputed from the bytes on disk on every
  run rather than trusted from a previous one.
- **Attribution is mandatory, not decoration.** dl-de/by-2-0 *requires* it. Every bundle
  names publisher, title, URL, licence and attribution in `election.toml`. A bundle without
  it may not be redistributed, and a test enforces this.
- **Bundle output is byte-stable.** CSV is written with `\n` endings and a trailing newline,
  and rows are sorted (national first, then Länder by official key, parties alphabetical
  within a unit). A re-ingest that changed nothing must produce a zero-line diff, so a diff
  shows a changed number rather than a changed line ending or a reshuffle.
- **`contents` lists exactly the files present.** The manifest must never overstate; a test
  compares it against the directory.
- **`notes` is emitted before `[source]`.** In TOML every key after a table header belongs
  to that table, so writing notes afterwards silently files them under `source.notes`,
  where no reader looks. This already happened once — the manifest still parsed, nothing
  complained, and the Berlin and Wiederholungswahl caveats were invisible. There is a test.
- **Tests never touch the network.** They read the committed bundles as a consumer would,
  with no ingestion code involved.

## What the source actually publishes

Everything derives from one file, the Bundeswahlleiterin's
`btw_ab49_datenbank_ergebnisse.csv`, preferred over the twenty-one per-election HTML pages
because it is *internally checkable*. Three seat series sit side by side and the difference
between them is why `bundeswahlleiterin.py` is longer than a pivot needs to be:

```
Sitze einschl. Abgeordnete BE   national, including the Berlin deputies
Sitze ohne Abgeordnete BE       national, excluding them
Sitze                           per Land (Gesamt / Wahlkreis / Landesliste)
```

**`ohne` is the declared result.** Before 1990 Berlin was outside the Wahlgebiet: its
deputies were delegated by the Abgeordnetenhaus, not elected, and held limited voting
rights. They appear in `einschl.` and in no Land column — which is why the Länder sum
exactly to `ohne` in every year.

**2021 overloads the same two columns for something else entirely.** There the `einschl.`
column carries the result *after* the Wiederholungswahl of 11 February 2024 (735 seats, FDP
91), not a Berlin-deputy count. The header does not say so; only the `Bemerkungen` cell
hints at it.

`seats_total_incl_berlin_deputies` is therefore read **only for years before 1990**. From
1990 on the column either repeats `ohne` or, in 2021, means something else — so the reader
never touches it, and 2021 needs no special case to come out right.

**The Wiederholungswahl is deliberately not modelled.** Not here, not in `wahlwerk`, not in
`wahlwerk-execute`: no field, no second variant, no event. `declared.csv` is the Hauptwahl
(736, FDP 92) and the re-run is one `notes` line. It is the only variant with a Land
breakdown — the 735 figure is published as a national total and nothing else — so recording
it would produce a bundle whose national and Land rows disagreed by a seat. If you add it
later, find a per-Land source first, and do not resurrect a parallel `seats_total_*` field
to hold it.

## Gotchas

- **`_RETRIEVED` in `bundles.py` is a hardcoded date string.** It is written into every
  manifest as `source.retrieved`. Bump it when you actually re-fetch, or the archive will
  claim a retrieval date it did not have.
- **`_LAW` in `bundles.py` covers 2025 and 2021 only.** The other nineteen elections emit no
  `law` key, deliberately: only the BWahlG versions the engine names in its build order are
  asserted. Do not guess the rest in to make the field look uniform.
- **The reader raises on a layout change rather than coping.** `_column` and the per-year
  row lookup both raise with "the source layout has changed". That is the intended
  behaviour — a silently re-shaped upstream file is the failure worth being loud about.
- **`land_unit` closes up `-\s+`, not all whitespace**, because the source's headers wrap
  *after the hyphen* (`Mecklenburg-\nVorpommern`). No German Land name contains a space, so
  this cannot merge two words that belong apart.
- **The en dash `–` is the source's "no data" marker**, not a hyphen. `_NO_DATA` carries a
  `noqa: RUF001` for exactly this reason.
- **`bundle_path` is defined in both repos** and is the one thing they must agree on.

## Layout

```
elections/de.bund/1949 … 2025/     the archive — committed, it is the product
  declared.csv                     unit,party,seats
  election.toml                    provenance, licence, checksum, notes, schema
src/wahlwerk_data/
  sources.py                       a published file, its licence, its checksum; fetch/cache
  bundeswahlleiterin.py            the reader — pivots the results database to long form
  laender.py                       the sixteen Länder as UnitIds, by official Destatis key
  parties.py                       source label -> registry PartyId, no fuzzy fallback
  bundles.py                       writes the bundle; owns bundle_path() and SCHEMA
  cli.py                           wahlwerk-ingest
tests/test_archive.py              reads the committed bundles as a consumer would
```

**One reader per publisher, not per election.** A new source is a new module beside
`bundeswahlleiterin.py`; `bundles.py`, `laender.py` and `parties.py` stay untouched.

## Bundle format

An election id maps to a path **by its last dot**: everything before it is the jurisdiction
and becomes the directory. `de.bund.2025` → `elections/de.bund/2025`, `de.nw.koeln.2025` →
`elections/de.nw.koeln/2025`. So the archive stays navigable as it grows instead of
flattening every level of government into one listing.

```
election.toml      provenance, licence, checksums, which law applies, schema version
units.csv          id,name,level,parent,seats,population
candidacies.csv    candidate,unit,kind,party,list_position
tally.csv.gz       unit,section,party,candidate,count        <- the votes
turnout.csv        unit,section,valid,invalid,eligible,cast
declared.csv       unit,party,seats                          <- the official result
```

Only `election.toml` and `declared.csv` exist today; the rest arrive with vote data.

`tally.csv` is the whole design: one row per counted quantity, an empty cell is null.
Cumulation (Hamburg, kommunal) is a larger `count` on a candidate row; panachage is rows
for several parties' candidates in one section. **A new Land quirk is new rows, never new
columns** — which is why the format survives sixteen Landeswahlleiter without versioning
itself to death.

Units are `de.bund` for the federal total and `de.bund.land.NN` by official Destatis key
(`01` Schleswig-Holstein … `16` Thüringen) — the key the sources are already organised by,
not an ordering invented here.

`election.toml` carries `schema = 1`. The engine declares the range it reads, so a format
change is a loud, testable break rather than a silent mis-parse. **Bump `SCHEMA` and tell
the engine** when the shape changes; never redefine a field in place.

## Language policy

Same as the engine, and it is not restated here in full: **translate the concept, keep the
term of art**. Identifiers and filenames are ASCII-transliterated (`laender.py`, party id
`gruene`); prose, data and output use correct German (`Länder`, `BÜNDNIS 90/DIE GRÜNEN`).
Docstrings, comments, tests and commit messages are English. The test for whether to keep a
German word is whether an official source uses it — the Bundeswahlleiterin, a statute or
the BVerfG. Never put an umlaut in `__all__` or an import.

Docstrings here explain *why the source is like this* — the Berlin deputies, the 2021
column overload, the pre-1952 Länder mapping. That context is the expensive part and it is
what stops the next reader from "fixing" a deliberate asymmetry.

## Sibling repositories

```
CODE/
  wahlwerk/          the engine       Apache-2.0
  wahlwerk-data/     the archive      dl-de/by-2-0   ← you are here
  wahlwerk-execute/  notebooks        depends on both
```

The dependency runs **one way**: this repo depends on `wahlwerk` for id types and the party
registry; the engine never depends on this repo. The engine's golden fixtures live inside
the engine so its CI runs offline. This is the *archive* — every election since 1949,
sixteen Länder, kommunal — and it is fetched on demand.

The engine resolves `$WAHLWERK_DATA` → `../wahlwerk-data` → its own cache. Cloning side by
side makes the middle path work with no configuration, but it is never a requirement.

## Adding an election

1. Add the polling date to `ELECTION_DAY` if the reader does not know it.
2. `uv run wahlwerk-ingest --check` first. Read every reported problem — a mismatch is
   information about the source, not noise to be silenced.
3. Any new party label raises. Add it to the **engine's** registry with a verified name.
4. Add the known seat total to `KNOWN_TOTALS` in the tests, taken from the historical
   record — *not* from the file you just ingested. That independence is the entire point.
5. Bump `_RETRIEVED` if you re-fetched.
6. Commit the bundle and the test in the same change.
