"""Tests for chat payload codecs (Task A1) against hand-built bytes."""
import time

import pytest

from p2p.chat import messages as c
from p2p.chat.chat import Chat
from p2p.common.interfaces import MembershipView
from p2p.common.protocol import MsgType
from p2p.membership.membership import Membership
from fake_transport import FakeNetwork


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


# =====================================================================
# Chat service tests (Task A3)
# =====================================================================
LOCAL = "127.0.0.1"


class StubMembership(MembershipView):
    """Minimal membership: a settable peer table and a manual event trigger."""

    def __init__(self):
        self.peers = {}
        self.callbacks = []

    def alive_peers(self):
        return dict(self.peers)

    def on_change(self, callback):
        self.callbacks.append(callback)

    def fire(self, event, peer_id):
        for cb in self.callbacks:
            cb(event, peer_id)


class ChatNode:
    """A Chat on a fake transport; ``got`` records (sender, text, private)."""

    def __init__(self, net, pid, port, **kw):
        self.pid, self.port = pid, port
        self.t = net.create(pid, port)
        self.t.start()
        self.mem = StubMembership()
        self.got = []
        self.chat = Chat(self.t, self.mem, pid,
                         lambda s, text, priv: self.got.append((s, text, priv)), **kw)

    def connect(self, *others):
        for o in others:
            self.mem.peers[o.pid] = (LOCAL, o.port)

    def feed(self, sender, seq, text):
        """Call the CHAT handler directly, as the transport would."""
        self.chat._on_chat(sender, (LOCAL, 6000 + sender), MsgType.CHAT, c.encode_chat(seq, text))

    def texts(self, sender=None):
        return [t for s, t, p in self.got if not p and (sender is None or s == sender)]


def wait_until(cond, timeout=3.0, step=0.01):
    """Poll cond() until true or timeout; return the final value."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(step)
    return cond()


def settle():
    """Give the delivery thread time to hand over everything queued."""
    time.sleep(0.15)


@pytest.fixture
def chats():
    """Collects ChatNodes and stops them at the end of the test."""
    created = []
    yield created
    for n in created:
        n.chat.stop()
        n.t.stop()


def make(chats, net, pid, **kw):
    node = ChatNode(net, pid, 5000 + pid, **kw)
    chats.append(node)
    return node


def test_messages_arrive_in_order(chats):
    net = FakeNetwork()
    a, b = make(chats, net, 1), make(chats, net, 2)
    a.connect(b)
    for i in range(1, 6):
        assert a.chat.send(f"m{i}") == i              # chat_seq starts at 1
    assert wait_until(lambda: len(b.got) == 5)
    assert b.got == [(1, f"m{i}", False) for i in range(1, 6)]
    assert a.got == []                                # no echo to the sender


def test_message_to_three_peers_all_arrive(chats):
    net = FakeNetwork()
    a = make(chats, net, 1)
    others = [make(chats, net, pid) for pid in (2, 3, 4)]
    a.connect(*others)
    a.chat.send("hello")
    a.chat.send("world")
    assert wait_until(lambda: all(len(o.got) == 2 for o in others))
    for o in others:
        assert o.got == [(1, "hello", False), (1, "world", False)]


def test_duplicate_is_dropped(chats):
    b = make(chats, FakeNetwork(), 2)
    b.feed(1, 1, "a")
    b.feed(1, 1, "a")                                 # duplicate of delivered
    b.feed(1, 2, "b")
    b.feed(1, 1, "a")                                 # late duplicate
    assert wait_until(lambda: len(b.got) == 2)
    settle()
    assert b.texts() == ["a", "b"]


def test_out_of_order_delivered_in_order(chats):
    b = make(chats, FakeNetwork(), 2)
    for seq in (1, 3, 2):
        b.feed(1, seq, f"m{seq}")
    assert wait_until(lambda: len(b.got) == 3)
    assert b.texts() == ["m1", "m2", "m3"]


def test_gap_waits_until_filled(chats):
    b = make(chats, FakeNetwork(), 2)
    b.feed(1, 1, "m1")
    b.feed(1, 4, "m4")
    b.feed(1, 3, "m3")
    settle()
    assert b.texts() == ["m1"]                        # 2 is missing: 3, 4 are held
    b.feed(1, 2, "m2")
    assert wait_until(lambda: len(b.got) == 4)
    assert b.texts() == ["m1", "m2", "m3", "m4"]


def test_first_seq_seen_starts_the_session(chats):
    # protocol.md 6.3: expected starts at the first chat_seq seen from a sender,
    # so a fresh sender whose first packet is seq 3 has its seq 1 and 2 dropped.
    b = make(chats, FakeNetwork(), 2)
    for seq in (3, 1, 2):
        b.feed(1, seq, f"m{seq}")
    settle()
    assert b.texts() == ["m3"]


def test_late_start_session_still_reorders(chats):
    b = make(chats, FakeNetwork(), 2)
    for seq in (5, 7, 6):
        b.feed(1, seq, f"m{seq}")
    assert wait_until(lambda: len(b.got) == 3)
    assert b.texts() == ["m5", "m6", "m7"]


def test_two_senders_are_independent(chats):
    b = make(chats, FakeNetwork(), 3)
    b.feed(1, 1, "a1")
    b.feed(2, 1, "b1")
    b.feed(2, 3, "b3")                                # held: waits for b2 only
    b.feed(1, 2, "a2")                                # sender 1 is not blocked
    settle()
    assert b.texts(1) == ["a1", "a2"]
    assert b.texts(2) == ["b1"]
    b.feed(2, 2, "b2")
    assert wait_until(lambda: b.texts(2) == ["b1", "b2", "b3"])


def test_late_joiner_receives_only_new_messages(chats):
    net = FakeNetwork()
    a, b, c_ = make(chats, net, 1), make(chats, net, 2), make(chats, net, 3)
    a.connect(b)
    for i in range(1, 4):
        a.chat.send(f"old{i}")
    assert wait_until(lambda: len(b.got) == 3)
    a.connect(c_)                                     # peer 3 joins the group now
    a.chat.send("new4")
    assert wait_until(lambda: len(c_.got) == 1)
    settle()
    assert c_.got == [(1, "new4", False)]             # none of old1..old3
    assert b.texts() == ["old1", "old2", "old3", "new4"]


@pytest.mark.parametrize("event", ["fail", "leave"])
def test_sender_state_resets_on_leave_or_fail(chats, event):
    b = ChatNode(FakeNetwork(), 2, 5002)
    chats.append(b)
    b.feed(1, 1, "a")
    b.feed(1, 2, "b")
    b.feed(1, 9, "stale")                             # buffered, must be forgotten
    settle()
    b.mem.fire(event, 1)
    b.feed(1, 1, "again")                             # sender restarted at seq 1
    assert wait_until(lambda: b.texts() == ["a", "b", "again"])
    settle()
    assert "stale" not in b.texts()


def test_buffer_is_capped(chats):
    b = make(chats, FakeNetwork(), 2, max_buffer=3)
    b.feed(1, 1, "m1")
    for seq in (3, 4, 5, 6):                          # 6 exceeds the cap of 3 and is dropped
        b.feed(1, seq, f"m{seq}")
    b.feed(1, 2, "m2")
    assert wait_until(lambda: len(b.got) == 5)
    settle()
    assert b.texts() == ["m1", "m2", "m3", "m4", "m5"]


def test_private_message_reaches_only_the_target(chats):
    net = FakeNetwork()
    a, b, c_ = make(chats, net, 1), make(chats, net, 2), make(chats, net, 3)
    a.connect(b, c_)
    a.chat.send_private(2, "psst")
    assert wait_until(lambda: len(b.got) == 1)
    settle()
    assert b.got == [(1, "psst", True)]
    assert c_.got == []
    assert a.chat._next_seq == 1                      # private messages use no chat_seq


def test_invalid_sends_raise_and_use_no_seq(chats):
    net = FakeNetwork()
    a, b = make(chats, net, 1), make(chats, net, 2)
    a.connect(b)
    with pytest.raises(ValueError):
        a.chat.send("x" * 1001)
    assert a.chat._next_seq == 1                      # failed send did not burn a seq
    with pytest.raises(ValueError):
        a.chat.send_private(2, "x" * 1001)
    with pytest.raises(ValueError):
        a.chat.send_private(99, "nobody home")
    a.chat.send("ok")
    assert wait_until(lambda: len(b.got) == 1)
    assert b.got == [(1, "ok", False)]


def test_bad_chat_payload_is_ignored(chats):
    b = make(chats, FakeNetwork(), 2)
    b.chat._on_chat(1, (LOCAL, 6001), MsgType.CHAT, b"\x00\x01")           # truncated
    b.chat._on_chat(1, (LOCAL, 6001), MsgType.CHAT, b"\x00\x00\x00\x01\xff")  # bad UTF-8
    b.feed(1, 1, "fine")
    assert wait_until(lambda: b.texts() == ["fine"])


def test_chat_over_real_membership_three_peers(chats):
    net = FakeNetwork()
    members, nodes = [], []
    try:
        for pid in (1, 2, 3):
            t = net.create(pid, 5000 + pid)
            t.start()
            m = Membership(t, pid, 5000 + pid, name=f"n{pid}",
                           bootstrap=None if pid == 1 else (LOCAL, 5001),
                           heartbeat_interval=0.1, peer_timeout=1.0)
            m.DISCOVER_INTERVAL = 0.1                 # instance override: fast first-peer start
            m.start()
            m.join()
            members.append(m)
            got = []
            ch = Chat(t, m, pid, lambda s, text, priv, g=got: g.append((s, text, priv)))
            nodes.append((t, ch, got))
        assert wait_until(lambda: all(len(m.alive_peers()) == 2 for m in members), 5.0)
        for i in range(1, 6):
            nodes[0][1].send(f"msg{i}")
        assert wait_until(lambda: len(nodes[1][2]) == 5 and len(nodes[2][2]) == 5, 5.0)
        expected = [(1, f"msg{i}", False) for i in range(1, 6)]
        assert nodes[1][2] == expected and nodes[2][2] == expected
    finally:
        for m in members:
            m.stop()
        for t, ch, _ in nodes:
            ch.stop()
            t.stop()
