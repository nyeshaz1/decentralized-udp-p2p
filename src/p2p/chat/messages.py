"""Payload codecs for chat messages (protocol.md section 3).

CHAT: u32 chat_seq + UTF-8 text (max 1000 bytes).
PRIVATE_MSG: UTF-8 text (max 1000 bytes).
"""
import struct
from typing import Tuple

# protocol.md: text is at most 1000 bytes (not defined in common/config.py)
MAX_TEXT_BYTES = 1000


def _enc_text(text: str) -> bytes:
    """Encode text as UTF-8; ValueError if it exceeds MAX_TEXT_BYTES."""
    data = text.encode("utf-8")
    if len(data) > MAX_TEXT_BYTES:
        raise ValueError(f"text too long (max {MAX_TEXT_BYTES} bytes)")
    return data


def encode_chat(chat_seq: int, text: str) -> bytes:
    """CHAT payload: u32 chat_seq (big-endian) + UTF-8 text."""
    return struct.pack(">I", chat_seq) + _enc_text(text)


def decode_chat(payload: bytes) -> Tuple[int, str]:
    """Return (chat_seq, text). Raises ValueError if malformed."""
    if len(payload) < 4:
        raise ValueError("truncated CHAT payload")
    (seq,) = struct.unpack(">I", payload[:4])
    rest = payload[4:]
    if len(rest) > MAX_TEXT_BYTES:
        raise ValueError("CHAT text too long")
    return seq, rest.decode("utf-8")


def encode_private(text: str) -> bytes:
    """PRIVATE_MSG payload: UTF-8 text."""
    return _enc_text(text)


def decode_private(payload: bytes) -> str:
    """Return the text of a PRIVATE_MSG. Raises ValueError if malformed."""
    if len(payload) > MAX_TEXT_BYTES:
        raise ValueError("PRIVATE_MSG text too long")
    return payload.decode("utf-8")
