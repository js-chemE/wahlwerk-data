"""Ingestion tooling for the wahlwerk election archive.

This package is *not* the archive. The archive is the committed ``elections/``
directory of bundles; this is the code that produces it from official sources and is
kept beside its output so that a bundle can always be rebuilt from the recorded URL and
checksum.

Direction of dependency matters: ``wahlwerk-data`` depends on ``wahlwerk`` for the
identifier types and the party registry, and the engine never depends on this repo. The
engine *reads* bundles; nothing in the engine writes one.

The one rule that governs everything here is in the repository README:

    **Readers reshape; they never compute.**

Rename and pivot as needed, but never derive a number. If the source publishes a
national total and a per-Land breakdown, store both as published -- do not sum the
Länder, even when the sum agrees. Any arithmetic in a reader is a bug, because deriving
seats is the engine's job and ``declared.csv`` is the independent check on it.
"""

from __future__ import annotations

__all__: list[str] = []
