"""Tests for membership payload codecs (Task A1) against hand-built bytes."""
import pytest

from p2p.membership import messages as m

FID = bytes(range(16))          # 00 01 02 ... 0f


def test_discover_bytes_and_roundtrip():
    assert m.encode_discover(5001) == b"\x13\x89"
    assert m.decode_discover(b"\x13\x89") == 5001
    assert m.decode_discover(m.encode_discover(65535)) == 65535


def test_discover_reply_bytes_and_roundtrip():
    assert m.encode_discover_reply(5002) == b"\x13\x8a"
    assert m.decode_discover_reply(b"\x13\x8a") == 5002


def test_join_bytes():
    assert m.encode_join(5001, "Ali") == b"\x13\x89\x03Ali"
    assert m.decode_join(b"\x13\x89\x03Ali") == (5001, "Ali")


def test_join_empty_name():
    assert m.encode_join(5001) == b"\x13\x89\x00"
    assert m.decode_join(b"\x13\x89\x00") == (5001, "")


def test_join_name_255_bytes_ok_and_256_rejected():
    name = "a" * 255
    payload = m.encode_join(7, name)
    assert payload[:3] == b"\x00\x07\xff" and len(payload) == 2 + 1 + 255
    assert m.decode_join(payload) == (7, name)
    with pytest.raises(ValueError):
        m.encode_join(7, "a" * 256)


def test_join_name_counts_utf8_bytes():
    # 128 two-byte characters = 256 bytes -> too long
    with pytest.raises(ValueError):
        m.encode_join(7, "é" * 128)
    assert m.decode_join(m.encode_join(7, "é" * 127)) == (7, "é" * 127)


def test_join_ack_status_id_in_use_is_one_byte():
    assert m.encode_join_ack(m.STATUS_ID_IN_USE) == b"\x01"
    ack = m.decode_join_ack(b"\x01")
    assert ack.status == 1 and ack.members == [] and ack.manifests == []


def test_join_ack_empty_member_list():
    raw = b"\x00" + b"\x00\x00" + b"\x00\x00" + b"\x00\x00\x00\x00"
    assert m.encode_join_ack(m.STATUS_OK) == raw
    ack = m.decode_join_ack(raw)
    assert ack.status == 0
    assert ack.members == [] and ack.manifests == [] and ack.chunk_map == []


def test_join_ack_hand_built_full():
    raw = (
        b"\x00"                                   # status OK
        b"\x00\x01"                               # n_members = 1
        b"\x00\x00\x00\x02" b"\x00\x00\x00\x00" b"\x13\x88" b"\x02Bo"
        b"\x00\x01"                               # n_files = 1
        b"\x00\x00\x00\x03" b"\xaa\xbb\xcc"       # manifest blob
        b"\x00\x00\x00\x01"                       # n_entries = 1
        + FID + b"\x00\x00\x00\x05" b"\x02"       # idx 5, 2 holders
        b"\x00\x00\x00\x01" b"\x00\x00\x00\x02"
    )
    built = m.encode_join_ack(
        0,
        members=[(2, "0.0.0.0", 5000, "Bo")],
        manifests=[b"\xaa\xbb\xcc"],
        chunk_map=[(FID, 5, [1, 2])],
    )
    assert built == raw
    ack = m.decode_join_ack(raw)
    assert ack.members == [(2, "0.0.0.0", 5000, "Bo")]
    assert ack.manifests == [b"\xaa\xbb\xcc"]
    assert ack.chunk_map == [(FID, 5, [1, 2])]


def test_join_ack_roundtrip_many():
    members = [(1, "192.168.1.10", 5001, "A"), (2, "10.0.0.2", 5002, ""),
               (3, "172.16.5.9", 6000, "x" * 255)]
    manifests = [b"", b"\x01" * 300]
    chunk_map = [(FID, 0, [1, 2]), (FID, 1, []), (bytes(16), 70000, [3])]
    ack = m.decode_join_ack(m.encode_join_ack(0, members, manifests, chunk_map))
    assert ack.members == members
    assert ack.manifests == manifests
    assert ack.chunk_map == chunk_map


def test_join_ack_bad_fid_rejected():
    with pytest.raises(ValueError):
        m.encode_join_ack(0, chunk_map=[(b"short", 0, [1])])


def test_join_ack_truncated_and_trailing_rejected():
    good = m.encode_join_ack(0, [(1, "1.2.3.4", 5, "n")], [b"ab"], [(FID, 0, [1])])
    for cut in range(1, len(good)):
        with pytest.raises(ValueError):
            m.decode_join_ack(good[:cut])
    with pytest.raises(ValueError):
        m.decode_join_ack(good + b"\x00")


def test_member_update_joined_bytes():
    raw = b"\x01" b"\x00\x00\x00\x09" b"\xc0\xa8\x01\x05" b"\x13\x89"
    assert m.encode_member_update(m.EVENT_JOINED, 9, "192.168.1.5", 5001) == raw
    assert m.decode_member_update(raw) == (1, 9, "192.168.1.5", 5001)


def test_member_update_failed_has_zero_ip_and_port():
    raw = b"\x03" b"\x00\x00\x00\x09" b"\x00\x00\x00\x00" b"\x00\x00"
    assert m.encode_member_update(m.EVENT_FAILED, 9) == raw
    # even if a caller passes an address, FAILED forces zeros
    assert m.encode_member_update(m.EVENT_FAILED, 9, "1.2.3.4", 99) == raw
    assert m.decode_member_update(raw) == (3, 9, "0.0.0.0", 0)


def test_leave_is_empty():
    assert m.encode_leave() == b""
    assert m.decode_leave(b"") is None
    with pytest.raises(ValueError):
        m.decode_leave(b"\x00")


def test_heartbeat_bytes_and_roundtrip():
    assert m.encode_heartbeat(258) == b"\x00\x00\x01\x02"
    assert m.decode_heartbeat(b"\x00\x00\x01\x02") == 258
    assert m.decode_heartbeat(m.encode_heartbeat(2**32 - 1)) == 2**32 - 1


def test_short_payloads_rejected():
    with pytest.raises(ValueError):
        m.decode_discover(b"\x01")
    with pytest.raises(ValueError):
        m.decode_join(b"\x13\x89")          # no name length byte
    with pytest.raises(ValueError):
        m.decode_join(b"\x13\x89\x05ab")    # name shorter than declared
    with pytest.raises(ValueError):
        m.decode_member_update(b"\x01\x00")
    with pytest.raises(ValueError):
        m.decode_heartbeat(b"\x00\x00")
