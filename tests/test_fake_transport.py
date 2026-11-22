import time
from fake_transport import FakeNetwork
from p2p.common.protocol import MsgType

def test_delivery_and_kill():
    net = FakeNetwork()
    a, b = net.create(1, 5001), net.create(2, 5002)
    got = []
    b.register_handler(MsgType.CHAT, lambda sid, addr, t, p: got.append((sid, p)))
    a.start(); b.start()
    a.send_reliable(b.addr, MsgType.CHAT, b"hi")
    time.sleep(0.3)
    assert got == [(1, b"hi")]
    b.kill()
    a.send_reliable(b.addr, MsgType.CHAT, b"x")
    time.sleep(0.3)
    assert got == [(1, b"hi")]