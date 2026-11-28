"""Sign In With Solana: strict parser and Ed25519 verifier.

Implements the ABNF format from the SIWS specification (read 2026-11-24):
https://github.com/phantom/sign-in-with-solana

The server never trusts client-supplied copies of the message fields. It parses the
signed message, compares each field with the server-issued challenge, and verifies
the Ed25519 signature with PyNaCl.
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import re
from dataclasses import dataclass

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58_INDEX = {char: index for index, char in enumerate(BASE58_ALPHABET)}

FIELD_ORDER = (
    "URI",
    "Version",
    "Chain ID",
    "Nonce",
    "Issued At",
    "Expiration Time",
    "Not Before",
    "Request ID",
    "Resources",
)
ADVANCED_FIELD_RE = re.compile(r"^(URI|Version|Chain ID|Nonce|Issued At|Expiration Time|Not Before|Request ID|Resources):(?: (.*))?$")


class SIWSError(ValueError):
    """Raised when a SIWS message is malformed or does not match the challenge."""


@dataclass(frozen=True)
class SIWSMessage:
    domain: str
    address: str
    statement: str | None
    uri: str | None
    version: str | None
    chain_id: str | None
    nonce: str
    issued_at: str | None
    expiration_time: str | None
    not_before: str | None
    request_id: str | None
    resources: tuple[str, ...]


def b58decode(value: str) -> bytes:
    if not value:
        raise SIWSError("Empty base58 string.")
    number = 0
    for char in value:
        try:
            number = number * 58 + BASE58_INDEX[char]
        except KeyError as exc:
            raise SIWSError("Invalid base58 character.") from exc
    body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    leading_zeroes = len(value) - len(value.lstrip("1"))
    return b"\x00" * leading_zeroes + body


def parse_message(message: str) -> SIWSMessage:
    if not isinstance(message, str) or not message:
        raise SIWSError("Message is required.")
    if "\r" in message:
        raise SIWSError("Only LF line endings are allowed.")

    lines = message.split("\n")
    if len(lines) < 2:
        raise SIWSError("Message is too short.")

    header = lines[0]
    if not header.endswith(" wants you to sign in with your Solana account:"):
        raise SIWSError("Invalid SIWS header.")
    domain = header[: -len(" wants you to sign in with your Solana account:")]
    if not domain:
        raise SIWSError("Missing domain.")

    address = lines[1]
    if not address:
        raise SIWSError("Missing address.")
    try:
        key_bytes = b58decode(address)
    except SIWSError:
        raise
    if len(key_bytes) != 32:
        raise SIWSError("Address is not a 32-byte Ed25519 public key.")
    # Reject non-canonical encodings (extra leading '1's).
    if base58encode(key_bytes) != address:
        raise SIWSError("Address is not canonically encoded.")

    rest = lines[2:]
    statement: str | None = None
    if rest:
        if rest[0] != "":
            raise SIWSError("Expected a blank line after the address.")
        rest = rest[1:]
        # A statement is present only when the next line is not an advanced field.
        # Without a statement, fields follow the single blank line directly.
        if rest and not ADVANCED_FIELD_RE.match(rest[0]):
            statement = rest[0]
            if statement.strip() == "":
                raise SIWSError("Empty statement.")
            rest = rest[1:]
            if not rest or rest[0] != "":
                raise SIWSError("Expected a blank line after the statement.")
            rest = rest[1:]

    fields: dict[str, str | None] = {}
    resources: list[str] = []
    expect_order: list[str] = []
    in_resources = False

    for line in rest:
        if in_resources:
            if not line.startswith("- "):
                raise SIWSError("Resources must be a list of '- <uri>' lines.")
            resources.append(line[2:])
            continue

        match = ADVANCED_FIELD_RE.match(line)
        if not match:
            raise SIWSError(f"Unexpected field: {line!r}")
        name, value = match.group(1), match.group(2)
        if name in fields:
            raise SIWSError(f"Duplicate field: {name}")
        fields[name] = value
        expect_order.append(name)

        if name == "Resources":
            in_resources = True
            if value not in (None, ""):
                raise SIWSError("Resources must be on a separate line.")

    if expect_order != list(FIELD_ORDER[: len(expect_order)]):
        raise SIWSError("SIWS fields are out of canonical order.")
    if "Nonce" not in fields or not fields["Nonce"]:
        raise SIWSError("Missing nonce.")

    return SIWSMessage(
        domain=domain,
        address=address,
        statement=statement,
        uri=fields.get("URI"),
        version=fields.get("Version"),
        chain_id=fields.get("Chain ID"),
        nonce=fields["Nonce"],
        issued_at=fields.get("Issued At"),
        expiration_time=fields.get("Expiration Time"),
        not_before=fields.get("Not Before"),
        request_id=fields.get("Request ID"),
        resources=tuple(resources),
    )


def base58encode(raw: bytes) -> str:
    number = int.from_bytes(raw, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = BASE58_ALPHABET[remainder] + encoded
    leading_zeroes = len(raw) - len(raw.lstrip(b"\x00"))
    return "1" * leading_zeroes + encoded


def decode_signature(signature: str | list[int]) -> bytes:
    if isinstance(signature, list):
        try:
            raw = bytes(signature)
        except ValueError as exc:
            raise SIWSError("Signature bytes are out of range.") from exc
    elif isinstance(signature, str):
        padded = signature + "=" * (-len(signature) % 4)
        try:
            raw = base64.b64decode(padded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise SIWSError("Signature must be base64 or a byte array.") from exc
    else:
        raise SIWSError("Signature must be base64 or a byte array.")
    if len(raw) != 64:
        raise SIWSError("Ed25519 signature must be 64 bytes.")
    return raw


def parse_iso8601(value: str) -> dt.datetime:
    if not value:
        raise SIWSError("Missing timestamp.")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as exc:
        raise SIWSError("Invalid ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def verify_message(
    message: str,
    signature: str | list[int],
    challenge,
    *,
    now: dt.datetime | None = None,
    issued_at_skew_seconds: int = 600,
    timestamp_tolerance_seconds: int = 120,
) -> str:
    """Verify a signed SIWS message against the server-issued challenge.

    Returns the signer address on success. Raises SIWSError otherwise.
    The nonce is NOT consumed here; the caller must consume it atomically.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    parsed = parse_message(message)

    if parsed.domain != challenge.domain:
        raise SIWSError("Domain does not match the challenge.")
    if parsed.statement != (challenge.statement or None):
        raise SIWSError("Statement does not match the challenge.")
    if parsed.uri != challenge.uri:
        raise SIWSError("URI does not match the challenge.")
    if parsed.chain_id != challenge.chain_id:
        raise SIWSError("Chain ID does not match the challenge.")
    if parsed.nonce != challenge.nonce:
        raise SIWSError("Nonce does not match the challenge.")
    if parsed.version not in (None, "1"):
        raise SIWSError("Unsupported SIWS version.")

    if parsed.issued_at is None:
        raise SIWSError("Issued At is required.")
    issued_at = parse_iso8601(parsed.issued_at)
    if abs((issued_at - challenge.issued_at).total_seconds()) > timestamp_tolerance_seconds:
        raise SIWSError("Issued At does not match the challenge.")
    if abs((now - issued_at).total_seconds()) > issued_at_skew_seconds:
        raise SIWSError("Issued At is outside the allowed clock skew.")

    if parsed.expiration_time is None:
        raise SIWSError("Expiration Time is required.")
    expiration = parse_iso8601(parsed.expiration_time)
    if expiration <= now:
        raise SIWSError("Sign-in message has expired.")
    if abs((expiration - challenge.expires_at).total_seconds()) > timestamp_tolerance_seconds:
        raise SIWSError("Expiration Time does not match the challenge.")

    if parsed.not_before:
        not_before = parse_iso8601(parsed.not_before)
        if now < not_before:
            raise SIWSError("Sign-in message is not valid yet.")

    signature_bytes = decode_signature(signature)
    verify_key = VerifyKey(b58decode(parsed.address))
    try:
        verify_key.verify(message.encode("utf-8"), signature_bytes)
    except BadSignatureError as exc:
        raise SIWSError("Signature verification failed.") from exc

    return parsed.address


def build_message(
    *,
    domain: str,
    address: str,
    statement: str | None,
    uri: str | None,
    version: str | None,
    chain_id: str | None,
    nonce: str,
    issued_at: str | None,
    expiration_time: str | None,
    not_before: str | None = None,
    request_id: str | None = None,
    resources: tuple[str, ...] = (),
) -> str:
    """Construct a SIWS message. Used by tests and by the legacy signMessage fallback."""
    message = f"{domain} wants you to sign in with your Solana account:\n{address}"
    if statement:
        message += f"\n\n{statement}"
    fields: list[str] = []
    if uri:
        fields.append(f"URI: {uri}")
    if version:
        fields.append(f"Version: {version}")
    if chain_id:
        fields.append(f"Chain ID: {chain_id}")
    if nonce:
        fields.append(f"Nonce: {nonce}")
    if issued_at:
        fields.append(f"Issued At: {issued_at}")
    if expiration_time:
        fields.append(f"Expiration Time: {expiration_time}")
    if not_before:
        fields.append(f"Not Before: {not_before}")
    if request_id:
        fields.append(f"Request ID: {request_id}")
    if resources:
        fields.append("Resources:")
        for resource in resources:
            fields.append(f"- {resource}")
    if fields:
        message += "\n\n" + "\n".join(fields)
    return message
