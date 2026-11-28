"""PDA derivation shared by the API and the indexer.

Uses solders so the addresses match the Anchor program exactly.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from solders.pubkey import Pubkey


class PdaError(ValueError):
    pass


def program_id() -> Pubkey:
    try:
        return Pubkey.from_string(settings.PROGRAM_ID)
    except Exception as exc:  # solders raises ValueError subclasses
        raise PdaError("PROGRAM_ID is not a valid Solana address.") from exc


def find_pda(seeds: list[bytes]) -> str:
    address, _bump = Pubkey.find_program_address(seeds, program_id())
    return str(address)


def registry_pda() -> str:
    return find_pda([b"registry"])


def reviewer_pda(wallet: str) -> str:
    return find_pda(
        [
            b"reviewer",
            bytes(Pubkey.from_string(registry_pda())),
            bytes(Pubkey.from_string(wallet)),
        ]
    )


def project_pda(project_id: uuid.UUID) -> str:
    return find_pda([b"project", project_id.bytes])


def milestone_pda(project_address: str, milestone_id: uuid.UUID) -> str:
    return find_pda(
        [b"milestone", bytes(Pubkey.from_string(project_address)), milestone_id.bytes]
    )


def criteria_pda(criteria_id: uuid.UUID) -> str:
    return find_pda([b"criteria", criteria_id.bytes])


def verification_pda(milestone_address: str, round_number: int, reviewer_wallet: str) -> str:
    if not 0 < round_number <= 65535:
        raise PdaError("Round must fit in u16 and be at least 1.")
    return find_pda(
        [
            b"verification",
            bytes(Pubkey.from_string(milestone_address)),
            round_number.to_bytes(2, "little"),
            bytes(Pubkey.from_string(reviewer_wallet)),
        ]
    )
