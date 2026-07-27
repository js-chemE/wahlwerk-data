"""Turning a source's party label into a stable id.

There is exactly one place party ids are minted: ``wahlwerk``'s registry. Every grouping
that has held an elected Bundestag seat since 1949 lives there, including the seven the
BTW 2025 seed did not know -- DP, KPD, WAV, Zentrum, GB/BHE, DKP/DRP and the residual
bucket "Andere Kreiswahlvorschläge".

They belong there rather than in per-bundle ``parties.csv`` files because a registry is a
*namespace authority*, not a convenience. If two bundles could each mint ``dp``, nothing
would notice when they disagreed; with one collection, the registry's own validator sees
every id and every alias at once and rejects a spelling that two parties claim.

``B90/Gr`` resolves to ``gruene``. In 1990 BÜNDNIS 90/GRÜNE and DIE GRÜNEN were separate
lists -- the threshold applied separately to the two Wahlgebiete, and the eastern list took
8 seats while the western one missed 5 % -- but that distinction is *territorial*, and the
tier structure already carries territory. Two lists in two Wahlgebiete are two units, not
two parties, and they merged in 1993 into the party the id names.

The FDV is deliberately absent. Its only seat in 1957 was a delegated Berlin one rather
than an elected mandate, so it never reaches ``declared.csv`` and needs no id.
"""

from __future__ import annotations

from wahlwerk.ids import PartyId
from wahlwerk.registry import PartyRegistry

__all__ = ["resolve_party"]


def resolve_party(label: str, registry: PartyRegistry) -> PartyId:
    """Turn a source label into a stable party id.

    There is no fuzzy fallback anywhere in wahlwerk: an unrecognised spelling that quietly
    became a new party is precisely how a phantom with seats and no votes appears. A label
    the registry cannot place is a data question for a human.
    """
    try:
        return registry.resolve(label).id
    except LookupError:
        raise LookupError(
            f"no party for source label {label!r}. Add it to wahlwerk's registry -- a row "
            f"in data/parties_de.csv with a verified name, and the label itself in "
            f"data/party_aliases_de.csv. Do not guess at a long name."
        ) from None
