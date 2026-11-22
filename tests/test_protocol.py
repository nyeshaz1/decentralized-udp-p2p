from p2p.common.protocol import Packet, pack, unpack, MsgType

def test_roundtrip():
    p = Packet(MsgType.CHAT, 7, seq=3, ack=2, flags=1, payload=b"hello")
    q = unpack(pack(p))
    assert q == p

def test_header_size():
    assert len(pack(Packet(MsgType.HEARTBEAT, 1))) == 24

def test_corruption_detected():
    b = bytearray(pack(Packet(MsgType.CHAT, 1, payload=b"abc")))
    b[-1] ^= 0xFF
    assert unpack(bytes(b)) is None

def test_bad_magic():
    b = bytearray(pack(Packet(MsgType.CHAT, 1)))
    b[0] = 0
    assert unpack(bytes(b)) is None
