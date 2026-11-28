import base64
import datetime as dt

from django.test import SimpleTestCase

from apps.accounts import siws


ACCOUNT = "9xQeWvG816bUx9EPjHmaT23yvVM7vA8c9HhF6k9mV1yZ"


def message_without_statement() -> str:
    return siws.build_message(
        domain="localhost:3000",
        address=ACCOUNT,
        statement=None,
        uri="http://localhost:3000",
        version="1",
        chain_id="devnet",
        nonce="0123456789abcdef0123456789abcdef",
        issued_at="2026-11-25T12:00:00Z",
        expiration_time="2026-11-25T12:05:00Z",
    )


class ParseMessageTests(SimpleTestCase):
    def test_parses_message_without_statement(self):
        parsed = siws.parse_message(message_without_statement())
        self.assertEqual(parsed.domain, "localhost:3000")
        self.assertEqual(parsed.address, ACCOUNT)
        self.assertIsNone(parsed.statement)
        self.assertEqual(parsed.nonce, "0123456789abcdef0123456789abcdef")
        self.assertEqual(parsed.chain_id, "devnet")
        self.assertEqual(parsed.uri, "http://localhost:3000")

    def test_parses_message_with_statement(self):
        message = siws.build_message(
            domain="localhost:3000",
            address=ACCOUNT,
            statement="Sign in to TrystSol.",
            uri="http://localhost:3000",
            version="1",
            chain_id="devnet",
            nonce="0123456789abcdef0123456789abcdef",
            issued_at="2026-11-25T12:00:00Z",
            expiration_time="2026-11-25T12:05:00Z",
        )
        parsed = siws.parse_message(message)
        self.assertEqual(parsed.statement, "Sign in to TrystSol.")
        self.assertEqual(parsed.nonce, "0123456789abcdef0123456789abcdef")

    def test_rejects_wrong_header(self):
        with self.assertRaises(siws.SIWSError):
            siws.parse_message(message_without_statement().replace("wants you to sign in", "wants to sign in"))

    def test_rejects_crlf(self):
        with self.assertRaises(siws.SIWSError):
            siws.parse_message(message_without_statement().replace("\n", "\r\n"))

    def test_rejects_duplicate_fields(self):
        message = message_without_statement().replace(
            "URI: http://localhost:3000", "URI: http://localhost:3000\nNonce: deadbeef"
        )
        with self.assertRaises(siws.SIWSError):
            siws.parse_message(message)

    def test_rejects_out_of_order_fields(self):
        message = message_without_statement().replace(
            "URI: http://localhost:3000\nVersion: 1",
            "Version: 1\nURI: http://localhost:3000",
        )
        with self.assertRaises(siws.SIWSError):
            siws.parse_message(message)

    def test_rejects_unknown_field(self):
        message = message_without_statement() + "\nInjected: value"
        with self.assertRaises(siws.SIWSError):
            siws.parse_message(message)

    def test_rejects_invalid_base58_address(self):
        message = message_without_statement().replace(ACCOUNT, "0" * 44)
        with self.assertRaises(siws.SIWSError):
            siws.parse_message(message)

    def test_rejects_non_32_byte_address(self):
        # Valid base58 but not a 32-byte key.
        message = message_without_statement().replace(ACCOUNT, "2" * 32)
        with self.assertRaises(siws.SIWSError):
            siws.parse_message(message)
