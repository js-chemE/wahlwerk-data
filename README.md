# wahlwerk-data

Normalised German election data for the [wahlwerk](https://github.com/js-chemE/wahlwerk)
engine. One directory per election, plain CSV, plus the ingestion code that produces it.

> **Status: seat distributions for all 21 Bundestagswahlen, 1949–2025.** Every bundle
> carries `declared.csv` — the official Sitzverteilung, nationally and per Land. No vote
> data yet: no `tally.csv`, no `units.csv`, no `candidacies.csv`. Each `election.toml`
> lists what it actually has in `contents`, so an absent file always means "not ingested"
> and never "this election had none".

## What is in the archive

| | | |
|---|---|---|
| Elections | 21 | every Bundestagswahl from 1949 to 2025 |
| Rows | 1 239 | `unit,party,seats`, national and per Land |
| Parties | 16 | distinct groupings that have won an elected seat |
| Source | 1 | the Bundeswahlleiterin's own results database |

Everything derives from one file, [`btw_ab49_datenbank_ergebnisse.csv`][src] — *"Wahl­be­rech­tigte,
Wählende, Stimmabgabe und Sitzverteilung bei den Bundestagswahlen seit 1949 nach Ländern"*.
It is preferred over the twenty-one per-election HTML pages for a reason that matters more
than convenience: it is internally checkable. The Länder sum exactly to the published
national total in all twenty-one elections, and each party's national figure equals the sum
of its Land figures — so a pivot that dropped or duplicated a row cannot pass silently.

[src]: https://www.bundeswahlleiterin.de/dam/jcr/24d8e745-920d-431a-893a-12805bc7ef40/btw_ab49_datenbank_ergebnisse.csv

## Four things the numbers do not say

Recorded in each affected `election.toml`, because collapsing any of them would make the
archive quietly wrong rather than loudly incomplete.

**Berlin, 1949–1987.** Berlin was outside the Wahlgebiet under the Viermächtestatus. Its
deputies — 8 in 1949, 22 from 1953 — were delegated by the Abgeordnetenhaus, not elected,
and held limited voting rights. `declared.csv` carries only elected seats, so 1949 is 402
and not 410; the other figure is `seats_total_incl_berlin_deputies`. A party could hold a
delegated seat and win nothing at the ballot box: the FDV's single seat in 1957 is exactly
that, and it correctly has no row in `declared.csv`.

**2021 was partially re-run, and the archive ignores it.** A Wiederholungswahl was held in
455 Berlin Wahlbezirke on 11 February 2024, after which the Bundestag held 735 seats with
the FDP on 91. `declared.csv` is the Hauptwahl of 26 September 2021 — 736 seats, FDP 92 —
and the re-run survives only as a `notes` line on that bundle. **Nothing in wahlwerk,
wahlwerk-data or wahlwerk-execute models it**: no field, no second variant, no event.

Two reasons to leave it out for now rather than carry both. The Hauptwahl is what the
*election* produced and what wahlwerk's M2 golden test targets; and it is the only variant
with a Land breakdown, because the 735 figure is published as a national total and nothing
else. Carrying it would mean a bundle whose national rows and Land rows disagreed by one
seat. Revisit when a per-Land source for the re-run exists.

> Watch the source here: it puts the revised figure in the `Sitze einschl. Abgeordnete BE`
> column, which for 2021 does not mean what its header says. The reader ignores that column
> for every year from 1990 on, which is what keeps 2021 honest without a special case.

**Länder before 1952.** The Bundeswahlleiterin maps Württemberg-Baden, Baden and
Württemberg-Hohenzollern onto Baden-Württemberg, which did not exist until 1952. Preserved
as published, and noted.

**Saarland before 1957.** It was not yet part of the Federal Republic and first votes in
the Bundestagswahl of 1957, so it has no rows in 1949 or 1953. A missing Land is a fact
about the territory, not a gap in the ingest.

These live in a top-level `notes` array in `election.toml`, emitted *before* the
`[source]` table — in TOML every key after a table header belongs to that table, so
writing them afterwards would file them under `source.notes`, where no reader looks.

## Rebuilding

```bash
uv sync
uv run wahlwerk-ingest             # fetch if needed, write elections/
uv run wahlwerk-ingest --refresh   # re-download the source first
uv run wahlwerk-ingest --check     # verify only, write nothing
uv run wahlwerk-ingest --root DIR  # write somewhere other than elections/
uv run pytest -q                   # 225 integrity tests over the committed bundles
uv run mypy && uv run ruff check .
```

The raw download is cached in `~/.cache/wahlwerk-data/`, outside the repository and never
committed. Its SHA-256 is recomputed from the bytes on disk on every run rather than
trusted from a previous one, so a hand-edited cache cannot produce a bundle claiming a
provenance it does not have.

Ingestion cross-checks every election before writing it, and a mismatch is reported per
election rather than raised, so one bad year does not hide the state of the other twenty.
Both sides of each check come from the source — Länder against the published national
total, per-party rows against the published grand total — so agreement means the pivot
lost and duplicated nothing.

The tests read the committed bundles as a consumer would, with no ingestion code involved,
and check the totals against the historical record rather than against the source the
bundles were built from — so a reader bug that shifted a column would fail rather than
agree with itself. The last two build a `Chamber` through the engine's own
`Chamber.from_archive`, which is the consumer path this archive exists to serve.

## Why this is a separate repository

- **Licence.** Official results are published under Datenlizenz Deutschland
  (dl-de/by-2-0), which requires attribution. The engine is Apache-2.0. Keeping them
  apart keeps both licences clean.
- **Clone size.** Git history is forever. Data grows every election; the engine should
  not carry that weight for anyone who only wants to `pip install wahlwerk`.
- **Cadence.** Data is append-only and arrives on the electoral calendar. Code changes
  when the abstraction does. Different repos, different release rhythms.

The engine does **not** depend on this repo. The golden fixtures it needs to verify
itself are committed inside wahlwerk, so its CI runs offline. This is the *archive*.

## Bundle format

An election id maps to a path by splitting on its **last dot**: everything before it is
the jurisdiction and becomes the directory, the last segment is the election.

```
elections/
  de.bund/1949/ … de.bund/2025/       de.bund.2025
  de.by/2023/                         de.by.2023          (not ingested yet)
  de.nw.koeln/2025/                   de.nw.koeln.2025    (not ingested yet)
```

So the archive stays navigable as it grows, instead of flattening every level of
government into one listing. `bundle_path()` in `src/wahlwerk_data/bundles.py` defines
the mapping once, and readers use it too.

```
de.bund/2025/
  election.toml      provenance, licence, checksums, which law applies, schema version
  units.csv          id,name,level,parent,seats,population
  candidacies.csv    candidate,unit,kind,party,list_position
  tally.csv.gz       unit,section,party,candidate,count        <- the votes
  turnout.csv        unit,section,valid,invalid,eligible,cast
  declared.csv       unit,party,seats                          <- the official result
```

`tally.csv` is the whole design. One row per counted quantity:

```csv
unit,section,party,candidate,count
de.bund.wk.001,zweitstimme,cdu,,45231
de.bund.wk.001,erststimme,,p.stein,52104
```

An empty cell is null. Cumulation (Hamburg, kommunal) is a larger `count` on a candidate
row; panachage is rows for several parties' candidates in one section. **A new Land quirk
is new rows, never new columns** — which is why the format survives sixteen
Landeswahlleiter without versioning itself to death.

`election.toml` carries `schema = 1`. The engine declares which schema versions it can
read, so a format change is a loud, testable break rather than a silent mis-parse.

Units in `declared.csv` are `de.bund` for the federal total and `de.bund.land.NN` for each
Land, numbered by the official Destatis Land key (`01` Schleswig-Holstein … `16` Thüringen)
— the key the sources are already organised by, not an ordering invented here.

**A bundle never mints a party id.** Every grouping that has held an elected seat since
1949 lives in wahlwerk's registry — `dp`, `kpd`, `wav`, `zentrum`, `gb-bhe`, `dkp-drp` and
`andere-kwv` alongside the parties of the current Bundestag. A registry is a namespace
authority, not a convenience: with one collection its validator sees every id and alias at
once and rejects a spelling two parties claim, which two independent bundles could never do.

Two entries are judgement calls, both argued in `src/wahlwerk_data/parties.py`:

- **`B90/Gr` resolves to `gruene`.** In 1990 BÜNDNIS 90/GRÜNE and DIE GRÜNEN were separate
  lists — the threshold applied separately to the two Wahlgebiete, so the eastern list took
  8 seats while the western one missed 5 % — but that distinction is *territorial*, and the
  tier structure already carries territory. Two lists in two Wahlgebiete are two units, not
  two parties, and they merged in 1993. The fold is safe only because the two never scored
  in the same election; if a source ever lists both with seats the reader raises rather than
  adding them up, because summing would be computing and the question is a human's.
- **`andere-kwv` is the source's residual bucket**, not a party: three Wahlkreise won in
  1949 by nominations outside the listed parties. Kept as published rather than split into
  three invented independents, and tagged `aggregate` so a reader can tell.

## Ingestion code

`src/wahlwerk_data/` sits beside its output so a bundle can always be rebuilt from the
recorded URL and checksum. The dependency runs one way — this repo depends on `wahlwerk`
for the id types and the party registry, and the engine never depends on this repo. The
engine *reads* bundles; nothing in the engine writes one.

```
src/wahlwerk_data/
  sources.py              a published file, its licence, its checksum; fetch + cache
  bundeswahlleiterin.py   the reader — pivots the results database to long form
  laender.py              the sixteen Länder as UnitIds, by official Destatis key
  parties.py              source label -> registry PartyId, no fuzzy fallback
  bundles.py              writes declared.csv and election.toml; owns bundle_path()
  cli.py                  wahlwerk-ingest: fetch, cross-check, write
```

One reader per publisher, not per election: a new source is a new module beside
`bundeswahlleiterin.py`, and everything downstream of it stays untouched.

## Rules for ingestion

- **Readers reshape; they never compute.** Rename and pivot as needed, but if a source
  publishes a percentage, store the count. If it publishes seat totals, those go in
  `declared.csv` and never into the tally. Any arithmetic in a reader is a bug — deriving
  seats is the engine's job, and `declared.csv` is what checks it.
- **Raw dumps are not committed.** `election.toml` records the source URL, retrieval date
  and SHA-256 of the file the bundle was built from. The bundle is reproducible from that;
  keeping the multi-megabyte original is not the archive's job.
- **Attribution is mandatory.** Every bundle names its source and licence in
  `election.toml`, per dl-de/by-2-0.

## Use

```bash
git clone https://github.com/js-chemE/wahlwerk-data.git
export WAHLWERK_DATA=$PWD/wahlwerk-data
```

The engine resolves `$WAHLWERK_DATA`, then a sibling `../wahlwerk-data`, then its own
fetched cache. Cloning next to `wahlwerk` makes the middle path work with no
configuration.

## Licence

Code and format: Apache-2.0 (see [LICENSE](LICENSE)).
Election data: Datenlizenz Deutschland – Namensnennung – Version 2.0 (dl-de/by-2-0),
attributed per bundle in `election.toml`.
