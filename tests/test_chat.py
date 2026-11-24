"""Tests for chat payload codecs (Task A1) against hand-built bytes."""
import pytest

from p2p.chat import messages as c


def test_chat_bytes():
    assert c.encode_chat(1, "hi") == b"\x00\x00\x00\x01hi"
    assert c.decode_chat(b"\x00\x00\x00\x01hi") == (1, "hi")


def test_chat_big_endian_seq():
    assert c.encode_chat(0x01020304, "")[:4] == b"\x01\x02\x03\x04"


def test_chat_roundtrip_unicode():
    text = "salam \u0633\u0644\u0627\u0645 \U0001F600"
    assert c.decode_chat(c.encode_chat(77, text)) == (77, text)


def test_chat_empty_text_ok():
    assert c.decode_chat(c.encode_chat(5, "")) == (5, "")


def test_chat_text_limit_1000_bytes():
    assert c.decode_chat(c.encode_chat(1, "a" * 1000))[1] == "a" * 1000
    with pytest.raises(ValueError):
        c.encode_chat(1, "a" * 1001)
    # the limit is in bytes, not characters: 501 two-byte chars = 1002 bytes
    with pytest.raises(ValueError):
        c.encode_chat(1, "\u00e9" * 501)


def test_chat_decode_rejects_bad_payloads():
    with pytest.raises(ValueError):
        c.decode_chat(b"\x00\x00")                      # truncated seq
    with pytest.raises(ValueError):
        c.decode_chat(b"\x00\x00\x00\x01\xff\xfe")      # invalid UTF-8
    with pytest.raises(ValueError):
        c.decode_chat(b"\x00\x00\x00\x01" + b"a" * 1001)


def test_private_bytes_and_roundtrip():
    assert c.encode_private("yo") == b"yo"
    assert c.decode_private(b"yo") == "yo"
    assert c.decode_private(c.encode_private("\u0633")) == "\u0633"


def test_private_limits():
    with pytest.raises(ValueError):
        c.encode_private("a" * 1001)
    with pytest.raises(ValueError):
        c.decode_private(b"\xff")
