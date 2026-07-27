"""Rebuild the archive from its sources.

    uv run wahlwerk-ingest            # fetch if needed, write elections/
    uv run wahlwerk-ingest --refresh  # re-download first
    uv run wahlwerk-ingest --check    # verify only, write nothing

The checks are the point of the ``--check`` mode and they run on every ingest anyway. They
are cross-source consistency tests, not assertions about numbers this code produced: the
Länder must sum to the published national total, and the per-party rows must sum to the
published grand total. Both sides come from the source, so agreement means the pivot did
not lose or duplicate a row. A mismatch is reported per election rather than raised, so one
bad year does not hide the state of the other twenty.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from wahlwerk_data.bundeswahlleiterin import Election, read_seats
from wahlwerk_data.bundles import write_bundle
from wahlwerk_data.laender import BUND
from wahlwerk_data.sources import BTW_AB49, fetch

__all__ = ["main"]


def _repo_root() -> Path:
    """The wahlwerk-data checkout: src/wahlwerk_data/cli.py -> three levels up."""
    return Path(__file__).resolve().parents[2]


def _check(election: Election) -> list[str]:
    """Cross-check one election. Returns a list of problems, empty when consistent."""
    problems: list[str] = []

    national = {e.party: e.seats for e in election.declared if e.unit == BUND}
    if sum(national.values()) != election.seats_total:
        problems.append(
            f"parties sum to {sum(national.values())}, source total is {election.seats_total}"
        )

    laender = sum(e.seats for e in election.declared if e.unit != BUND)
    if laender != election.seats_total:
        problems.append(f"Länder sum to {laender}, source total is {election.seats_total}")

    for party, seats in national.items():
        in_laender = sum(
            e.seats for e in election.declared if e.unit != BUND and e.party == party
        )
        if in_laender != seats:
            problems.append(f"{party}: {seats} nationally but {in_laender} across Länder")

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="re-download the source")
    parser.add_argument("--check", action="store_true", help="verify only, write nothing")
    parser.add_argument("--root", type=Path, default=None, help="archive root")
    args = parser.parse_args(argv)

    path, digest = fetch(BTW_AB49, refresh=args.refresh)
    print(f"source  {path}")
    print(f"sha256  {digest}\n")

    elections = read_seats(path)
    root = args.root or (_repo_root() / "elections")

    failed = 0
    for election in elections:
        problems = _check(election)
        failed += bool(problems)
        parties = len(election.national)
        berlin = election.seats_total_incl_berlin_deputies
        extra = (
            f"  (+{berlin - election.seats_total} delegated Berlin deputies)"
            if berlin is not None
            else ""
        )
        status = "FAIL" if problems else "ok"
        print(
            f"{status:>4}  {election.id}  {election.seats_total:>4} seats"
            f"  {parties:>2} parties{extra}"
        )
        for problem in problems:
            print(f"        ! {problem}")
        if not problems and not args.check:
            write_bundle(election, root, BTW_AB49, digest)

    print(f"\n{len(elections)} elections, {failed} with problems")
    if not args.check and not failed:
        print(f"written to {root}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
