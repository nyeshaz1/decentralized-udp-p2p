import collections
import logging
import random
import socket
import struct
import threading
import time

from p2p.common import config
from p2p.common.interfaces import Transport
from p2p.common.protocol import (
    Packet, pack, unpack, MsgType, F_RELIABLE, F_MORE_FRAG
)

log = logging.getLogger("transport")

MAX_LOGICAL = 256 * 1024
RTO_FIXED = 1.0          # Monday: fixed timeout. Tuesday: RFC 6298.


class _Entry:
    """One sent-but-unacknowledged packet."""

    def __init__(self, data, now):
        self.data = data
        self.first_sent = now
        self.last_sent = now
        self.retries = 0
        self.retransmitted = False
        self.sacked = False
        self.dupcount = 0


class _PeerState:
    """Transport state for one remote address."""

    def __init__(self):
        self.session = 0
        self.send_base = 1
        self.next_seq = 1
        self.unacked = {}                    # seq -> _Entry
        self.queue = collections.deque()     # (type, flags, payload) waiting for window
        self.recv_base = 1
        self.recv_buf = {}                   # seq -> Packet
        self.frag = bytearray()

        # self.rto = RTO_FIXED fixed 1 seconnd makes code slow
        #fixed 1s timer cases slownedd
        self.rto = 1.0
        self.srtt = None
        self.rttvar = None


class ReliableUDP(Transport):
    """UDP transport with Selective Repeat reliability (protocol.md section 4)."""

    def __init__(self, my_id, port, loss_rate=0.0, bind_ip="0.0.0.0", seed=None):
        self.my_id = my_id
        self.port = port
        self.loss_rate = loss_rate
        self.rng = random.Random(seed)
        self.session = random.randint(1, 255)
        self.handlers = {}
        self._unreachable_cb = None
        self._running = False
        self._threads = []
        self.lock = threading.RLock()
        self.peers = {}                      # addr -> _PeerState
        self.stats = {"sent": 0, "retransmitted": 0, "bytes_delivered": 0}

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind((bind_ip, port))
        self.sock.settimeout(0.1)

        self.disc_sock = None
        try:
            self.disc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.disc_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                self.disc_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            self.disc_sock.bind((bind_ip, config.DISCOVERY_PORT))
            self.disc_sock.settimeout(0.1)
        except OSError as e:
            log.warning("[%s] cannot bind discovery port: %s", my_id, e)
            self.disc_sock = None

    # ---------------- public interface ----------------

    def register_handler(self, msg_type, handler):
        self.handlers[int(msg_type)] = handler

    def set_unreachable_handler(self, cb):
        self._unreachable_cb = cb

    def start(self):
        self._running = True
        for s in (self.sock, self.disc_sock):
            if s is not None:
                t = threading.Thread(target=self._recv_loop, args=(s,), daemon=True)
                t.start()
                self._threads.append(t)
        t = threading.Thread(target=self._timer_loop, daemon=True)
        t.start()
        self._threads.append(t)

    def stop(self):
        self._running = False
        for t in self._threads:
            t.join(timeout=1)
        for s in (self.sock, self.disc_sock):
            if s is not None:
                s.close()

    def send_unreliable(self, addr, msg_type, payload):
        pkt = Packet(int(msg_type), self.my_id, seq=0, payload=payload,
                     session=self.session)
        self._send_raw(tuple(addr), pack(pkt))

    def broadcast(self, msg_type, payload, port):
        pkt = Packet(int(msg_type), self.my_id, seq=0, payload=payload,
                     session=self.session)
        self._send_raw(("255.255.255.255", port), pack(pkt))

    def send_reliable(self, addr, msg_type, payload):
        """Ordered exactly-once delivery. Fragments payloads over 1024 bytes."""
        if len(payload) > MAX_LOGICAL:
            raise ValueError("message larger than 256 KiB")

        addr = tuple(addr)
        size = config.MAX_PAYLOAD
        frags = [payload[i:i + size] for i in range(0, len(payload), size)] or [b""]

        with self.lock:
            st = self.peers.setdefault(addr, _PeerState())
            for i, frag in enumerate(frags):
                flags = F_RELIABLE | (F_MORE_FRAG if i < len(frags) - 1 else 0)
                st.queue.append((int(msg_type), flags, frag))
            self._pump(addr, st)

    # ---------------- sending side ----------------

    def _send_raw(self, addr, data):
        if self.loss_rate and self.rng.random() < self.loss_rate:
            return
        try:
            self.sock.sendto(data, addr)
            self.stats["sent"] += 1
        except OSError as e:
            log.debug("[%s] send error: %s", self.my_id, e)

    def _pump(self, addr, st):
        """Move queued packets into the window and send them. Call with lock held."""
        while st.queue and st.next_seq < st.send_base + config.WINDOW:
            mtype, flags, frag = st.queue.popleft()
            pkt = Packet(mtype, self.my_id, seq=st.next_seq, ack=st.recv_base,
                         flags=flags, payload=frag, session=self.session)
            data = pack(pkt)
            st.unacked[st.next_seq] = _Entry(data, time.monotonic())
            st.next_seq += 1
            self._send_raw(addr, data)

    def _process_cum_ack(self, addr, st, ack):
        """Remove everything below `ack` from the window. Lock held."""
        if ack <= st.send_base:
            return
        now = time.monotonic()
        newly = sorted(s for s in st.unacked if s < ack)
        entries = [st.unacked.pop(s) for s in newly]
        clean = bool(entries) and all(
            not e.retransmitted and not e.sacked for e in entries)
        if clean:
            self._update_rtt(st, now - entries[-1].last_sent)
        elif st.srtt is not None:
            # progress was made: drop any backoff, go back to the measured RTO
            st.rto = min(config.RTO_MAX,
                         max(config.RTO_MIN, st.srtt + 4 * st.rttvar))
        st.send_base = min(st.unacked) if st.unacked else max(st.next_seq, ack)
        self._pump(addr, st)

    def _update_rtt(self, st, sample):
        """RFC 6298: update SRTT/RTTVAR and RTO from one RTT sample."""
        if st.srtt is None:
            st.srtt = sample
            st.rttvar = sample / 2
        else:
            st.rttvar = 0.75 * st.rttvar + 0.25 * abs(st.srtt - sample)
            st.srtt = 0.875 * st.srtt + 0.125 * sample

        st.rto = min(config.RTO_MAX, max(config.RTO_MIN, st.srtt + 4 * st.rttvar))

    def _handle_ack(self, addr, st, pkt):
        self._process_cum_ack(addr, st, pkt.ack)
        if len(pkt.payload) == 8:
            base, bitmap = struct.unpack(">II", pkt.payload)
            for i in range(32):
                if bitmap & (1 << i):
                    e = st.unacked.get(base + i)
                    if e:
                        e.sacked = True
            # fast retransmit: 3+ packets after the oldest were SACKed
            first = st.unacked.get(st.send_base)
            if first is not None and not first.sacked:
                sacked_after = sum(1 for e in st.unacked.values() if e.sacked)
                if sacked_after >= 3:
                    now = time.monotonic()
                    if now - first.last_sent > 0.05:     # avoid resending too often
                        first.last_sent = now
                        first.retransmitted = True
                        self.stats["retransmitted"] += 1
                        self._send_raw(addr, first.data)

    def _timer_loop(self):
        while self._running:
            time.sleep(0.02)
            now = time.monotonic()
            with self.lock:
                for addr, st in list(self.peers.items()):
                    backoff = False
                    for seq, e in list(st.unacked.items()):
                        if e.sacked or now - e.last_sent < st.rto:
                            continue
                        e.last_sent = now
                        e.retries += 1
                        e.retransmitted = True
                        self.stats["retransmitted"] += 1
                        self._send_raw(addr, e.data)
                        if seq == st.send_base:
                            backoff = True
                    if backoff:
                        st.rto = min(config.RTO_MAX, st.rto * 2)

    # ---------------- receiving side ----------------

    def _recv_loop(self, sock):
        while self._running:
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break

            if self.loss_rate and self.rng.random() < self.loss_rate:
                continue

            pkt = unpack(data)
            if pkt is None:
                continue

            if pkt.sender_id == self.my_id and pkt.type == MsgType.DISCOVER:
                continue

            try:
                self._on_packet(pkt, addr)
            except Exception:
                log.exception("[%s] packet processing error", self.my_id)

    def _touch(self, addr, session):
        """Get state for addr; reset it if the peer restarted (new session)."""
        st = self.peers.get(addr)
        if st is None:
            st = self.peers[addr] = _PeerState()

        if st.session == 0:
            st.session = session
        elif session != st.session:
            log.info("[%s] session change from %s, resetting state", self.my_id, addr)
            st = self.peers[addr] = _PeerState()
            st.session = session

        return st

    def _on_packet(self, pkt, addr):
        deliveries = []
        with self.lock:
            st = self._touch(addr, pkt.session)
            if pkt.type == MsgType.ACK:
                self._handle_ack(addr, st, pkt)
            elif pkt.flags & F_RELIABLE:
                deliveries = self._handle_reliable(addr, st, pkt)
            else:
                deliveries = [(pkt.type, pkt.payload)]

        for mtype, payload in deliveries:      # handlers run outside the lock
            self._dispatch(pkt.sender_id, addr, mtype, payload)

    def _handle_reliable(self, addr, st, pkt):
        """Buffer, deliver in order, drop duplicates, ACK. Lock held."""
        self._process_cum_ack(addr, st, pkt.ack)
        out = []
        seq = pkt.seq

        if seq >= st.recv_base + config.WINDOW:
            return out                          # outside window: drop

        if seq >= st.recv_base and seq not in st.recv_buf:
            st.recv_buf[seq] = pkt
            while st.recv_base in st.recv_buf:
                p = st.recv_buf.pop(st.recv_base)
                st.recv_base += 1
                st.frag.extend(p.payload)
                if not (p.flags & F_MORE_FRAG):
                    out.append((p.type, bytes(st.frag)))
                    st.frag = bytearray()

        self._send_ack(addr, st)                # ACK every reliable packet, even duplicates
        return out

    def _send_ack(self, addr, st):
        base = st.recv_base + 1
        bitmap = 0
        for i in range(32):
            if (base + i) in st.recv_buf:
                bitmap |= 1 << i

        pkt = Packet(MsgType.ACK, self.my_id, seq=0, ack=st.recv_base,
                     payload=struct.pack(">II", base, bitmap), session=self.session)
        self._send_raw(addr, pack(pkt))

    def _dispatch(self, sender_id, addr, msg_type, payload):
        self.stats["bytes_delivered"] += len(payload)
        h = self.handlers.get(int(msg_type))
        if h is None:
            return
        try:
            h(sender_id, addr, int(msg_type), payload)
        except Exception:
            log.exception("[%s] handler error for type %s", self.my_id, msg_type)