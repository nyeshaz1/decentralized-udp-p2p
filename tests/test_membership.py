"""Tests for membership payload codecs (Task A1) against hand-built bytes."""
import threading
import time

import pytest

from p2p.common.protocol import MsgType
from p2p.membership import messages as m
from p2p.membership.membership import Membership, MembershipError
from fake_transport import FakeNetwork

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


# =====================================================================
# Membership service tests (Task A2) using FakeNetwork
# =====================================================================
FAST = dict(heartbeat_interval=0.1, peer_timeout=0.6)
LOCAL = "127.0.0.1"


@pytest.fixture(autouse=True)
def fast_timers(monkeypatch):
    """Shorten discovery/join/leave waits so tests run in a second or two."""
    monkeypatch.setattr(Membership, "DISCOVER_INTERVAL", 0.1)
    monkeypatch.setattr(Membership, "JOIN_TIMEOUT", 2.0)
    monkeypatch.setattr(Membership, "LEAVE_WAIT", 0.05)


@pytest.fixture
def nodes():
    """Collects started nodes and stops them at the end of the test."""
    created = []
    yield created
    for n in created:
        n.m.stop()
        n.t.stop()


class Node:
    """A Membership plus its fake transport and a log of on_change events."""

    def __init__(self, net, pid, port, bootstrap=None, **kw):
        self.pid, self.port = pid, port
        self.t = net.create(pid, port)
        self.t.start()
        opts = dict(FAST)
        opts.update(kw)
        self.m = Membership(self.t, pid, port, name=f"n{pid}", bootstrap=bootstrap, **opts)
        self.events = []
        self.m.on_change(lambda e, p: self.events.append((e, p)))
        self.m.start()

    def count(self, event, pid):
        return self.events.count((event, pid))


def wait_until(cond, timeout=5.0, step=0.02):
    """Poll cond() until true or timeout; return the final value."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(step)
    return cond()


def start_group(net, nodes, n, use_bootstrap, **kw):
    """Start peer 1 alone, then peers 2..n joining via bootstrap or broadcast."""
    first = Node(net, 1, 5001, **kw)
    nodes.append(first)
    first.m.join()
    for pid in range(2, n + 1):
        boot = (LOCAL, 5001) if use_bootstrap else None
        node = Node(net, pid, 5000 + pid, bootstrap=boot, **kw)
        nodes.append(node)
        node.m.join()
    return nodes[-n:]


def converged(group):
    ids = {n.pid for n in group}
    return all(set(n.m.alive_peers()) == ids - {n.pid} for n in group)


def test_four_peers_converge_via_bootstrap(nodes):
    group = start_group(FakeNetwork(), nodes, 4, use_bootstrap=True)
    assert wait_until(lambda: converged(group), 5.0)
    assert group[0].m.alive_peers()[2] == (LOCAL, 5002)
    assert group[3].m.peer_name(1) == "n1"
    # on_change events are delivered asynchronously: wait for them, then
    # check that each join was reported exactly once (no duplicates).
    def all_joins_seen():
        return all(n.count("join", o.pid) >= 1
                   for n in group for o in group if o is not n)
    assert wait_until(all_joins_seen, 3.0)
    time.sleep(0.3)
    for n in group:
        for other in group:
            if other is not n:
                assert n.count("join", other.pid) == 1


def test_four_peers_converge_via_broadcast_discover(nodes):
    group = start_group(FakeNetwork(), nodes, 4, use_bootstrap=False)
    assert wait_until(lambda: converged(group), 5.0)


def test_first_peer_runs_alone_when_nobody_answers(nodes):
    solo = Node(FakeNetwork(), 1, 5001)
    nodes.append(solo)
    solo.m.join()
    assert solo.m.alive_peers() == {}


def test_crashed_peer_detected_by_everyone(nodes):
    group = start_group(FakeNetwork(), nodes, 4, use_bootstrap=True)
    assert wait_until(lambda: converged(group), 5.0)
    group[3].t.kill()                                # peer 4 crashes, no LEAVE
    survivors = group[:3]
    limit = FAST["peer_timeout"] + 2.0
    assert wait_until(lambda: all(n.count("fail", 4) >= 1 for n in survivors), limit)
    time.sleep(0.5)                                  # let gossip arrive
    for n in survivors:
        assert n.count("fail", 4) == 1               # idempotent: exactly once
        assert 4 not in n.m.alive_peers()
        assert len(n.m.alive_peers()) == 2


def test_graceful_leave_fires_leave_immediately(nodes):
    group = start_group(FakeNetwork(), nodes, 3, use_bootstrap=True)
    assert wait_until(lambda: converged(group), 5.0)
    group[2].m.leave()
    assert wait_until(lambda: all(n.count("leave", 3) == 1 for n in group[:2]), 1.0)
    for n in group[:2]:
        assert n.count("fail", 3) == 0
        assert 3 not in n.m.alive_peers()


def test_duplicate_id_rejected(nodes):
    net = FakeNetwork()
    a = Node(net, 1, 5001)
    nodes.append(a)
    a.m.join()
    b = Node(net, 2, 5002, bootstrap=(LOCAL, 5001))
    nodes.append(b)
    b.m.join()
    dup_of_b = Node(net, 2, 5003, bootstrap=(LOCAL, 5001))
    nodes.append(dup_of_b)
    with pytest.raises(MembershipError):
        dup_of_b.m.join()
    dup_of_a = Node(net, 1, 5004, bootstrap=(LOCAL, 5001))
    nodes.append(dup_of_a)
    with pytest.raises(MembershipError):
        dup_of_a.m.join()
    assert a.m.alive_peers() == {2: (LOCAL, 5002)}   # table untouched


def test_bootstrap_unreachable_raises(nodes, monkeypatch):
    monkeypatch.setattr(Membership, "JOIN_TIMEOUT", 0.3)
    n = Node(FakeNetwork(), 1, 5001, bootstrap=(LOCAL, 5999))
    nodes.append(n)
    with pytest.raises(MembershipError, match="bootstrap unreachable"):
        n.m.join()


def test_state_provider_data_reaches_joiner_consumer(nodes):
    net = FakeNetwork()
    fid = bytes(range(16))
    a = Node(net, 1, 5001)
    nodes.append(a)
    a.m.state_provider = lambda: ([b"manifest-1"], [(fid, 3, [1])])
    a.m.join()
    got = []
    b = Node(net, 2, 5002, bootstrap=(LOCAL, 5001))
    nodes.append(b)
    b.m.state_consumer = lambda manifests, chunk_map: got.append((manifests, chunk_map))
    b.m.join()
    assert got == [([b"manifest-1"], [(fid, 3, [1])])]


def test_heartbeat_from_unknown_peer_is_ignored(nodes):
    net = FakeNetwork()
    a = Node(net, 1, 5001)
    nodes.append(a)
    stranger = net.create(9, 5009)
    stranger.start()
    stranger.send_unreliable((LOCAL, 5001), MsgType.HEARTBEAT, m.encode_heartbeat(1))
    time.sleep(0.3)
    assert a.m.alive_peers() == {}


def test_30_percent_heartbeat_loss_causes_no_false_failures(nodes):
    # 10:1 timeout/interval ratio. (With the default 5:1 ratio a run of 5 lost
    # heartbeats happens by chance about 0.24% of the time at 30% loss.)
    net = FakeNetwork(loss=0.3, seed=7)
    group = start_group(net, nodes, 4, use_bootstrap=True,
                        heartbeat_interval=0.05, peer_timeout=0.5)
    assert wait_until(lambda: converged(group), 5.0)
    time.sleep(3.0)                                  # ~60 heartbeats per pair
    assert converged(group)
    for n in group:
        assert not [e for e in n.events if e[0] in ("fail", "leave")]
