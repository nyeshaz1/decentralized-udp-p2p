
import os
import time
from p2p.transport.reliable_udp import ReliableUDP
from p2p.common.protocol import MsgType


def wait_until(cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def make_pair(pa, pb):
    a, b = ReliableUDP(1, pa), ReliableUDP(2, pb)
    a.start(); b.start()
    return a, b


def test_unreliable_delivery():
    a, b = make_pair(47001, 47002)
    got = []
    b.register_handler(MsgType.HEARTBEAT, lambda s, ad, t, p: got.append((s, p)))
    try:
        a.send_unreliable(("127.0.0.1", 47002), MsgType.HEARTBEAT, b"\x00\x00\x00\x01")
        assert wait_until(lambda: len(got) == 1)
        assert got == [(1, b"\x00\x00\x00\x01")]
    finally:
        a.stop(); b.stop()


def test_ten_messages_in_order_once():
    a, b = make_pair(47011, 47012)
    got = []
    b.register_handler(MsgType.CHAT, lambda s, ad, t, p: got.append(p))
    try:
        for i in range(10):
            a.send_reliable(("127.0.0.1", 47012), MsgType.CHAT, b"msg%d" % i)
        assert wait_until(lambda: len(got) >= 10)
        time.sleep(0.5)  # allow any duplicate to show up
        assert got == [b"msg%d" % i for i in range(10)]
    finally:
        a.stop(); b.stop()


def test_200kb_message_intact():
    a, b = make_pair(47021, 47022)
    got = []
    b.register_handler(MsgType.CHUNK_DATA, lambda s, ad, t, p: got.append(p))
    data = os.urandom(200 * 1024)
    try:
        a.send_reliable(("127.0.0.1", 47022), MsgType.CHUNK_DATA, data)
        assert wait_until(lambda: len(got) == 1)
        assert got[0] == data
    finally:
        a.stop(); b.stop()


def test_1mb_with_20_percent_loss():
    a = ReliableUDP(1, 47031, loss_rate=0.2, seed=11)
    b = ReliableUDP(2, 47032, loss_rate=0.2, seed=22)
    a.start(); b.start()
    got = []
    b.register_handler(MsgType.CHUNK_DATA, lambda s, ad, t, p: got.append(p))
    data = os.urandom(200 * 1024)
    try:
        for _ in range(5):
            a.send_reliable(("127.0.0.1", 47032), MsgType.CHUNK_DATA, data)
        assert wait_until(lambda: len(got) == 5, timeout=90)
        assert all(g == data for g in got)
        assert a.stats["retransmitted"] > 0
    finally:
        a.stop(); b.stop()
