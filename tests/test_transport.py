import time
from p2p.transport.reliable_udp import ReliableUDP
from p2p.common.protocol import MsgType


def test_unreliable_delivery():
    a = ReliableUDP(1, 47001)
    b = ReliableUDP(2, 47002)
    got = []
    b.register_handler(MsgType.HEARTBEAT, lambda s, ad, t, p: got.append((s, p)))
    a.start(); b.start()
    try:
        a.send_unreliable(("127.0.0.1", 47002), MsgType.HEARTBEAT, b"\x00\x00\x00\x01")
        time.sleep(0.3)
        assert got == [(1, b"\x00\x00\x00\x01")]
    finally:
        a.stop(); b.stop()