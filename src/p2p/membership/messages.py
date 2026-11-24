"""Payload codecs for membership messages (protocol.md section 3).

All integers are big-endian. str8 = u8 length + UTF-8 bytes, ip4 = 4 bytes,
fid = 16 bytes. Decoders raise ValueError on truncated or malformed payloads.
"""
import socket
import struct
from dataclasses import dataclass, field
from typing import List, Tuple

# JOIN_ACK status codes
STATUS_OK = 0
STATUS_ID_IN_USE = 1

# MEMBER_UPDATE events (2 is unused: a graceful leave uses LEAVE)
EVENT_JOINED = 1
EVENT_FAILED = 3

FID_LEN = 16


# ---------------------------------------------------------------- helpers
def _ip_to_bytes(ip: str) -> bytes:
    """Convert a dotted IPv4 string to 4 bytes."""
    try:
        return socket.inet_aton(ip)
    except OSError as exc:
        raise ValueError(f"bad IPv4 address: {ip!r}") from exc


def _bytes_to_ip(raw: bytes) -> str:
    """Convert 4 bytes to a dotted IPv4 string."""
    return socket.inet_ntoa(raw)


def _enc_str8(text: str) -> bytes:
    """Encode text as str8; ValueError if longer than 255 UTF-8 bytes."""
    data = text.encode("utf-8")
    if len(data) > 255:
        raise ValueError("str8 too long (max 255 bytes)")
    return bytes([len(data)]) + data


class _Reader:
    """Sequential reader over a payload that checks bounds."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def take(self, n: int) -> bytes:
        """Return the next n bytes or raise ValueError if truncated."""
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError("truncated payload")
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def unpack(self, fmt: str):
        """Read one struct-formatted value group (big-endian)."""
        size = struct.calcsize(fmt)
        return struct.unpack(fmt, self.take(size))

    def str8(self) -> str:
        """Read a str8 field."""
        n = self.take(1)[0]
        return self.take(n).decode("utf-8")

    def done(self) -> None:
        """Raise ValueError if bytes are left over."""
        if self.pos != len(self.data):
            raise ValueError("unexpected trailing bytes")


# -------------------------------------------- DISCOVER / DISCOVER_REPLY
def encode_discover(port: int) -> bytes:
    """DISCOVER payload: u16 port."""
    return struct.pack(">H", port)


def decode_discover(payload: bytes) -> int:
    """Return the port from a DISCOVER payload."""
    r = _Reader(payload)
    (port,) = r.unpack(">H")
    r.done()
    return port


def encode_discover_reply(port: int) -> bytes:
    """DISCOVER_REPLY payload: u16 port."""
    return struct.pack(">H", port)


def decode_discover_reply(payload: bytes) -> int:
    """Return the port from a DISCOVER_REPLY payload."""
    r = _Reader(payload)
    (port,) = r.unpack(">H")
    r.done()
    return port


# ------------------------------------------------------------------- JOIN
def encode_join(port: int, name: str = "") -> bytes:
    """JOIN payload: u16 port + str8 name."""
    return struct.pack(">H", port) + _enc_str8(name)


def decode_join(payload: bytes) -> Tuple[int, str]:
    """Return (port, name) from a JOIN payload."""
    r = _Reader(payload)
    (port,) = r.unpack(">H")
    name = r.str8()
    r.done()
    return port, name


# --------------------------------------------------------------- JOIN_ACK
@dataclass
class JoinAck:
    """Decoded JOIN_ACK.

    members:   list of (peer_id, ip_str, port, name)
    manifests: list of opaque FILE_MANIFEST payload blobs
    chunk_map: list of (fid bytes, idx, [holder ids])
    """
    status: int = STATUS_OK
    members: List[Tuple[int, str, int, str]] = field(default_factory=list)
    manifests: List[bytes] = field(default_factory=list)
    chunk_map: List[Tuple[bytes, int, List[int]]] = field(default_factory=list)


def encode_join_ack(status: int, members=(), manifests=(), chunk_map=()) -> bytes:
    """JOIN_ACK payload. For status != 0 only the status byte is sent."""
    out = bytearray([status])
    if status != STATUS_OK:
        return bytes(out)
    out += struct.pack(">H", len(members))
    for peer_id, ip, port, name in members:
        out += struct.pack(">I", peer_id) + _ip_to_bytes(ip)
        out += struct.pack(">H", port) + _enc_str8(name)
    out += struct.pack(">H", len(manifests))
    for blob in manifests:
        out += struct.pack(">I", len(blob)) + blob
    out += struct.pack(">I", len(chunk_map))
    for fid, idx, holders in chunk_map:
        if len(fid) != FID_LEN:
            raise ValueError("fid must be 16 bytes")
        if len(holders) > 255:
            raise ValueError("too many holders (max 255)")
        out += fid + struct.pack(">IB", idx, len(holders))
        for h in holders:
            out += struct.pack(">I", h)
    return bytes(out)


def decode_join_ack(payload: bytes) -> JoinAck:
    """Decode a JOIN_ACK payload into a JoinAck."""
    r = _Reader(payload)
    (status,) = r.unpack(">B")
    if status != STATUS_OK:
        r.done()
        return JoinAck(status=status)
    ack = JoinAck(status=status)
    (n_members,) = r.unpack(">H")
    for _ in range(n_members):
        (peer_id,) = r.unpack(">I")
        ip = _bytes_to_ip(r.take(4))
        (port,) = r.unpack(">H")
        ack.members.append((peer_id, ip, port, r.str8()))
    (n_files,) = r.unpack(">H")
    for _ in range(n_files):
        (length,) = r.unpack(">I")
        ack.manifests.append(r.take(length))
    (n_entries,) = r.unpack(">I")
    for _ in range(n_entries):
        fid = r.take(FID_LEN)
        idx, n_holders = r.unpack(">IB")
        holders = [r.unpack(">I")[0] for _ in range(n_holders)]
        ack.chunk_map.append((fid, idx, holders))
    r.done()
    return ack


# ---------------------------------------------------------- MEMBER_UPDATE
def encode_member_update(event: int, peer_id: int, ip: str = "0.0.0.0",
                         port: int = 0) -> bytes:
    """MEMBER_UPDATE payload: u8 event, u32 peer_id, ip4, u16 port.

    For EVENT_FAILED the ip is zeros and the port is 0 (forced here).
    """
    if event == EVENT_FAILED:
        ip, port = "0.0.0.0", 0
    return struct.pack(">BI", event, peer_id) + _ip_to_bytes(ip) + struct.pack(">H", port)


def decode_member_update(payload: bytes) -> Tuple[int, int, str, int]:
    """Return (event, peer_id, ip_str, port)."""
    r = _Reader(payload)
    event, peer_id = r.unpack(">BI")
    ip = _bytes_to_ip(r.take(4))
    (port,) = r.unpack(">H")
    r.done()
    return event, peer_id, ip, port


# ------------------------------------------------------------------ LEAVE
def encode_leave() -> bytes:
    """LEAVE payload: empty."""
    return b""


def decode_leave(payload: bytes) -> None:
    """LEAVE has no payload; raise ValueError if bytes are present."""
    _Reader(payload).done()


# -------------------------------------------------------------- HEARTBEAT
def encode_heartbeat(tick: int) -> bytes:
    """HEARTBEAT payload: u32 tick."""
    return struct.pack(">I", tick)


def decode_heartbeat(payload: bytes) -> int:
    """Return the tick from a HEARTBEAT payload."""
    r = _Reader(payload)
    (tick,) = r.unpack(">I")
    r.done()
    return tick
