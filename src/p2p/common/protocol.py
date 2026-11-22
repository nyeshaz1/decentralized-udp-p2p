import struct, zlib
from enum import IntEnum
from dataclasses import dataclass
from .config import MAGIC, VERSION, HEADER_SIZE, MAX_PAYLOAD

_FMT = ">HBBBBIIIHI"
assert struct.calcsize(_FMT) == HEADER_SIZE

class MsgType(IntEnum):
    DISCOVER = 0x01; DISCOVER_REPLY = 0x02; JOIN = 0x03; JOIN_ACK = 0x04
    MEMBER_UPDATE = 0x05; LEAVE = 0x06; HEARTBEAT = 0x07
    CHAT = 0x10; PRIVATE_MSG = 0x11
    ACK = 0x20
    FILE_MANIFEST = 0x30; CHUNK_STORE = 0x31; CHUNK_REQUEST = 0x32
    CHUNK_DATA = 0x33; CHUNK_ERROR = 0x34; REPLICA_UPDATE = 0x35

F_RELIABLE, F_ACK_ONLY, F_MORE_FRAG, F_ENCRYPTED = 0x01, 0x02, 0x04, 0x08

@dataclass
class Packet:
    type: int
    sender_id: int
    seq: int = 0
    ack: int = 0
    flags: int = 0
    payload: bytes = b""

def pack(p: Packet) -> bytes:
    if len(p.payload) > MAX_PAYLOAD:
        raise ValueError("payload too large")
    hdr0 = struct.pack(_FMT, MAGIC, VERSION, p.type, p.flags, 0,
                       p.sender_id, p.seq, p.ack, len(p.payload), 0)
    crc = zlib.crc32(hdr0 + p.payload) & 0xFFFFFFFF
    return hdr0[:-4] + struct.pack(">I", crc) + p.payload

def unpack(data: bytes):
    """Return Packet or None if invalid (bad magic/version/length/CRC)."""
    if len(data) < HEADER_SIZE:
        return None
    magic, ver, typ, flags, _r, sid, seq, ack, plen, crc = struct.unpack(_FMT, data[:HEADER_SIZE])
    payload = data[HEADER_SIZE:]
    if magic != MAGIC or ver != VERSION or plen != len(payload):
        return None
    hdr0 = data[:HEADER_SIZE - 4] + b"\x00\x00\x00\x00"
    if zlib.crc32(hdr0 + payload) & 0xFFFFFFFF != crc:
        return None
    return Packet(typ, sid, seq, ack, flags, payload)
