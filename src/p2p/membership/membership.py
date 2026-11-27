"""Peer discovery, membership table, heartbeat and failure detection (Task A2).

Implements protocol.md sections 5 and 6.1. Uses only the Transport interface.

Threading rules:
  * Transport handlers return fast and never send while holding ``_lock``.
  * User callbacks (on_change) run on a separate dispatcher thread, never
    while the peer-table lock is held.
  * All background threads are daemon threads; stop() ends them.
"""
import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

from p2p.common import config
from p2p.common.interfaces import MembershipView, Transport
from p2p.common.protocol import MsgType
from p2p.membership import messages as msg

log = logging.getLogger("p2p.membership")

Addr = Tuple[str, int]

# Timings from the leader's answers (not in the frozen config.py).
DISCOVER_INTERVAL = 2.0   # seconds between DISCOVER broadcasts
DISCOVER_TRIES = 3        # DISCOVERs before running alone
JOIN_TIMEOUT = 6.0        # wait for JOIN_ACK after sending JOIN
LEAVE_WAIT = 1.0          # wait after sending LEAVE before stopping
ANY_IP = "0.0.0.0"        # replier's own entry in JOIN_ACK


class MembershipError(Exception):
    """Raised by join() when the group cannot be joined.

    Raised for ID_IN_USE, an unreachable bootstrap peer, or a discovered
    peer that never answers JOIN. node.py and cli.py catch this.
    """


@dataclass
class _Peer:
    """One row of the peer table."""
    addr: Addr
    name: str
    last_seen: float


class Membership(MembershipView):
    """Membership service: who is in the group, and who just joined/left/failed."""

    # Class attributes so tests can shorten them with monkeypatch.
    DISCOVER_INTERVAL = DISCOVER_INTERVAL
    DISCOVER_TRIES = DISCOVER_TRIES
    JOIN_TIMEOUT = JOIN_TIMEOUT
    LEAVE_WAIT = LEAVE_WAIT

    def __init__(self, transport: Transport, my_id: int, my_port: int,
                 name: str = "", bootstrap: Optional[Addr] = None,
                 heartbeat_interval: Optional[float] = None,
                 peer_timeout: Optional[float] = None):
        """Create the service (nothing runs until start()).

        Raises ValueError if ``name`` is longer than 255 UTF-8 bytes.
        """
        if len(name.encode("utf-8")) > 255:
            raise ValueError("name too long (max 255 UTF-8 bytes)")
        self.transport = transport
        self.my_id = my_id
        self.my_port = my_port
        self.name = name
        self.bootstrap = tuple(bootstrap) if bootstrap else None
        self.heartbeat_interval = (config.HEARTBEAT_INTERVAL
                                   if heartbeat_interval is None else heartbeat_interval)
        self.peer_timeout = (config.PEER_TIMEOUT
                             if peer_timeout is None else peer_timeout)

        # Hooks used by storage (Hamza); defaults per the leader.
        self.state_provider: Callable[[], tuple] = lambda: ([], [])
        self.state_consumer: Callable[[list, list], None] = lambda manifests, chunk_map: None

        self._lock = threading.Lock()
        self._peers: Dict[int, _Peer] = {}
        self._callbacks = []
        self._events: "queue.Queue" = queue.Queue()
        self._stop_evt = threading.Event()
        self._hb_thread: Optional[threading.Thread] = None
        self._dispatch_thread: Optional[threading.Thread] = None
        self._tick = 0

        # join() state
        self._reply_evt = threading.Event()
        self._first_reply: Optional[Addr] = None
        self._ack_evt = threading.Event()
        self._acked = False
        self._join_error: Optional[MembershipError] = None

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        """Register transport handlers and start the heartbeat/dispatcher threads."""
        t = self.transport
        t.register_handler(MsgType.DISCOVER, self._on_discover)
        t.register_handler(MsgType.DISCOVER_REPLY, self._on_discover_reply)
        t.register_handler(MsgType.JOIN, self._on_join)
        t.register_handler(MsgType.JOIN_ACK, self._on_join_ack)
        t.register_handler(MsgType.MEMBER_UPDATE, self._on_member_update)
        t.register_handler(MsgType.LEAVE, self._on_leave)
        t.register_handler(MsgType.HEARTBEAT, self._on_heartbeat)
        self._dispatch_thread = threading.Thread(
            target=self._dispatch_loop, name=f"member-events-{self.my_id}", daemon=True)
        self._hb_thread = threading.Thread(
            target=self._heartbeat_loop, name=f"member-hb-{self.my_id}", daemon=True)
        self._dispatch_thread.start()
        self._hb_thread.start()
        log.info("[peer %d] membership started", self.my_id)

    def stop(self) -> None:
        """Stop the background threads (safe to call more than once)."""
        self._stop_evt.set()
        self._events.put(None)
        for th in (self._hb_thread, self._dispatch_thread):
            if th is not None and th.is_alive() and th is not threading.current_thread():
                th.join(timeout=1.0)
        log.info("[peer %d] membership stopped", self.my_id)

    # ----------------------------------------------------------------- join
    def join(self) -> None:
        """Join the group (protocol.md 6.1).

        With ``bootstrap`` send JOIN there; otherwise broadcast DISCOVER up to
        DISCOVER_TRIES times and run alone if nobody answers.
        Raises MembershipError for ID_IN_USE or an unreachable peer.
        """
        if self.bootstrap is not None:
            self._send_join(self.bootstrap)
            if not self._ack_evt.wait(self.JOIN_TIMEOUT):
                raise MembershipError("bootstrap unreachable")
        else:
            target = self._discover()
            if target is None:
                log.info("[peer %d] nobody answered DISCOVER, running alone", self.my_id)
                return
            self._send_join(target)
            if not self._ack_evt.wait(self.JOIN_TIMEOUT):
                raise MembershipError("no JOIN_ACK from discovered peer")
        if self._join_error is not None:
            raise self._join_error
        log.info("[peer %d] joined, peers=%s", self.my_id, sorted(self.alive_peers()))

    def _discover(self) -> Optional[Addr]:
        """Broadcast DISCOVER and return the address of the first replier, or None."""
        for attempt in range(self.DISCOVER_TRIES):
            self.transport.broadcast(MsgType.DISCOVER,
                                     msg.encode_discover(self.my_port),
                                     config.DISCOVERY_PORT)
            log.debug("[peer %d] DISCOVER sent (try %d)", self.my_id, attempt + 1)
            if self._reply_evt.wait(self.DISCOVER_INTERVAL):
                return self._first_reply
        return None

    def _send_join(self, addr: Addr) -> None:
        """Send JOIN reliably to addr."""
        self._send(addr, MsgType.JOIN, msg.encode_join(self.my_port, self.name))

    # ---------------------------------------------------------------- leave
    def leave(self) -> None:
        """Send LEAVE reliably to every alive peer, wait up to LEAVE_WAIT, then stop."""
        with self._lock:
            targets = [p.addr for p in self._peers.values()]
        for addr in targets:
            self._send(addr, MsgType.LEAVE, msg.encode_leave())
        if targets:
            time.sleep(self.LEAVE_WAIT)
        self.stop()

    # ------------------------------------------------------------- queries
    def alive_peers(self) -> dict:
        """Return {peer_id: (ip, port)} of alive peers (excluding self)."""
        with self._lock:
            return {pid: p.addr for pid, p in self._peers.items()}

    def on_change(self, callback: Callable[[str, int], None]) -> None:
        """Register callback(event, peer_id), event in 'join' | 'leave' | 'fail'."""
        with self._lock:
            self._callbacks.append(callback)

    def peer_name(self, peer_id: int) -> str:
        """Return the display name of a peer ('' if unknown)."""
        if peer_id == self.my_id:
            return self.name
        with self._lock:
            p = self._peers.get(peer_id)
            return p.name if p else ""

    def report_unreachable(self, addr: Addr) -> None:
        """Transport callback: the peer at addr exceeded MAX_RETRIES -> FAILED."""
        addr = tuple(addr)
        with self._lock:
            pid = next((i for i, p in self._peers.items() if p.addr == addr), None)
        if pid is not None:
            log.info("[peer %d] transport reports peer %d unreachable", self.my_id, pid)
            self._fail_peer(pid)

    # ------------------------------------------------------------ internals
    def _send(self, addr: Addr, msg_type: int, payload: bytes, reliable: bool = True) -> None:
        """Send via the transport; never raises."""
        try:
            if reliable:
                self.transport.send_reliable(addr, msg_type, payload)
            else:
                self.transport.send_unreliable(addr, msg_type, payload)
        except Exception:
            log.exception("[peer %d] send of type %s to %s failed", self.my_id, msg_type, addr)

    def _fire(self, event: str, peer_id: int) -> None:
        """Queue an on_change event (delivered by the dispatcher thread)."""
        self._events.put((event, peer_id))

    def _dispatch_loop(self) -> None:
        """Deliver queued events to callbacks, outside every lock."""
        while True:
            item = self._events.get()
            if item is None:
                return
            with self._lock:
                callbacks = list(self._callbacks)
            for cb in callbacks:
                try:
                    cb(*item)
                except Exception:
                    log.exception("[peer %d] on_change callback failed", self.my_id)

    def _touch(self, peer_id: int) -> None:
        """Refresh last_seen of a known peer (unknown peers are never added here)."""
        with self._lock:
            p = self._peers.get(peer_id)
            if p is not None:
                p.last_seen = time.monotonic()

    def _fail_peer(self, peer_id: int) -> None:
        """Remove a peer as FAILED, fire 'fail' and gossip MEMBER_UPDATE(FAILED)."""
        with self._lock:
            if self._peers.pop(peer_id, None) is None:
                return                       # already failed/left: idempotent
            others = [p.addr for p in self._peers.values()]
        log.info("[peer %d] peer %d FAILED", self.my_id, peer_id)
        self._fire("fail", peer_id)
        payload = msg.encode_member_update(msg.EVENT_FAILED, peer_id)
        for addr in others:
            self._send(addr, MsgType.MEMBER_UPDATE, payload)

    def _heartbeat_loop(self) -> None:
        """Every interval: send HEARTBEAT to alive peers, then expire silent ones."""
        while not self._stop_evt.wait(self.heartbeat_interval):
            try:
                self._tick = (self._tick + 1) & 0xFFFFFFFF
                payload = msg.encode_heartbeat(self._tick)
                now = time.monotonic()
                with self._lock:
                    targets = [(pid, p.addr) for pid, p in self._peers.items()]
                    expired = [pid for pid, p in self._peers.items()
                               if now - p.last_seen > self.peer_timeout]
                for pid in expired:
                    self._fail_peer(pid)
                for pid, addr in targets:
                    if pid not in expired:
                        self._send(addr, MsgType.HEARTBEAT, payload, reliable=False)
            except Exception:
                log.exception("[peer %d] heartbeat loop error", self.my_id)

    # ------------------------------------------------------------- handlers
    def _on_discover(self, sender_id, addr, msg_type, payload) -> None:
        """Answer a DISCOVER with a unicast DISCOVER_REPLY (ignore our own)."""
        if sender_id == self.my_id:
            return
        try:
            port = msg.decode_discover(payload)
        except ValueError:
            log.warning("[peer %d] bad DISCOVER from %s", self.my_id, addr)
            return
        self._touch(sender_id)
        self._send((addr[0], port), MsgType.DISCOVER_REPLY,
                   msg.encode_discover_reply(self.my_port), reliable=False)

    def _on_discover_reply(self, sender_id, addr, msg_type, payload) -> None:
        """Remember only the first DISCOVER_REPLY; ignore the rest."""
        if sender_id == self.my_id:
            return
        try:
            port = msg.decode_discover_reply(payload)
        except ValueError:
            log.warning("[peer %d] bad DISCOVER_REPLY from %s", self.my_id, addr)
            return
        if not self._reply_evt.is_set():
            self._first_reply = (addr[0], port)
            self._reply_evt.set()

    def _on_join(self, sender_id, addr, msg_type, payload) -> None:
        """Handle JOIN: add the peer, reply JOIN_ACK, gossip MEMBER_UPDATE(JOINED)."""
        try:
            port, name = msg.decode_join(payload)
        except ValueError:
            log.warning("[peer %d] bad JOIN from %s", self.my_id, addr)
            return
        peer_addr = (addr[0], port)
        if sender_id == self.my_id:                       # id clash with me
            self._send(peer_addr, MsgType.JOIN_ACK, msg.encode_join_ack(msg.STATUS_ID_IN_USE))
            return
        with self._lock:
            existing = self._peers.get(sender_id)
            conflict = existing is not None and existing.addr != peer_addr
            is_new = existing is None
            if not conflict:
                if is_new:
                    self._peers[sender_id] = _Peer(peer_addr, name, time.monotonic())
                else:
                    existing.last_seen = time.monotonic()
                    existing.name = name
                members = [(self.my_id, ANY_IP, self.my_port, self.name)]
                members += [(pid, p.addr[0], p.addr[1], p.name)
                            for pid, p in self._peers.items() if pid != sender_id]
                update_targets = [p.addr for pid, p in self._peers.items() if pid != sender_id]
        if conflict:
            log.info("[peer %d] JOIN from %s rejected: id %d in use", self.my_id, peer_addr, sender_id)
            self._send(peer_addr, MsgType.JOIN_ACK, msg.encode_join_ack(msg.STATUS_ID_IN_USE))
            return
        try:
            manifests, chunk_map = self.state_provider()
        except Exception:
            log.exception("[peer %d] state_provider failed", self.my_id)
            manifests, chunk_map = [], []
        self._send(peer_addr, MsgType.JOIN_ACK,
                   msg.encode_join_ack(msg.STATUS_OK, members, manifests, chunk_map))
        if is_new:
            log.info("[peer %d] peer %d joined from %s", self.my_id, sender_id, peer_addr)
            self._fire("join", sender_id)
            update = msg.encode_member_update(msg.EVENT_JOINED, sender_id, peer_addr[0], peer_addr[1])
            for a in update_targets:
                self._send(a, MsgType.MEMBER_UPDATE, update)

    def _on_join_ack(self, sender_id, addr, msg_type, payload) -> None:
        """Handle JOIN_ACK: on the first OK merge members, hand state over, JOIN everyone."""
        try:
            ack = msg.decode_join_ack(payload)
        except ValueError:
            log.warning("[peer %d] bad JOIN_ACK from %s", self.my_id, addr)
            return
        self._touch(sender_id)
        if ack.status != msg.STATUS_OK:
            self._join_error = MembershipError(f"peer id {self.my_id} is already in use in the group")
            self._ack_evt.set()
            return
        with self._lock:
            first = not self._acked
            self._acked = True
            new_ids, join_targets = [], []
            if first:
                now = time.monotonic()
                for pid, ip, port, name in ack.members:
                    if pid == self.my_id or pid in self._peers:
                        continue
                    if ip == ANY_IP:                      # replier's own entry
                        ip = addr[0]
                    self._peers[pid] = _Peer((ip, port), name, now)
                    new_ids.append(pid)
                join_targets = [p.addr for pid, p in self._peers.items() if pid != sender_id]
        if not first:
            return                                        # later ACKs: nothing more to do
        try:
            self.state_consumer(ack.manifests, ack.chunk_map)
        except Exception:
            log.exception("[peer %d] state_consumer failed", self.my_id)
        for pid in new_ids:
            self._fire("join", pid)
        for a in join_targets:
            self._send_join(a)
        self._ack_evt.set()

    def _on_member_update(self, sender_id, addr, msg_type, payload) -> None:
        """Handle gossip: JOINED adds an unknown peer, FAILED removes a known one."""
        try:
            event, pid, ip, port = msg.decode_member_update(payload)
        except ValueError:
            log.warning("[peer %d] bad MEMBER_UPDATE from %s", self.my_id, addr)
            return
        self._touch(sender_id)
        if pid == self.my_id:
            return
        if event == msg.EVENT_JOINED:
            with self._lock:
                if pid in self._peers:
                    return
                self._peers[pid] = _Peer((ip, port), "", time.monotonic())
            log.info("[peer %d] peer %d joined (gossip)", self.my_id, pid)
            self._fire("join", pid)
        elif event == msg.EVENT_FAILED:
            self._fail_peer_from_gossip(pid)

    def _fail_peer_from_gossip(self, pid: int) -> None:
        """Remove a peer reported FAILED by someone else (gossip is not forwarded)."""
        with self._lock:
            if self._peers.pop(pid, None) is None:
                return                                    # already failed: ignore
        log.info("[peer %d] peer %d FAILED (gossip)", self.my_id, pid)
        self._fire("fail", pid)

    def _on_leave(self, sender_id, addr, msg_type, payload) -> None:
        """Handle LEAVE: remove the peer at once and fire 'leave'."""
        with self._lock:
            removed = self._peers.pop(sender_id, None)
        if removed is not None:
            log.info("[peer %d] peer %d left", self.my_id, sender_id)
            self._fire("leave", sender_id)

    def _on_heartbeat(self, sender_id, addr, msg_type, payload) -> None:
        """Refresh last_seen; heartbeats from peers not in the table are ignored."""
        self._touch(sender_id)
