import logging
import os
import random
import socket
import threading
import time

from p2p.common import config
from p2p.common.interfaces import Transport
from p2p.common.protocol import Packet, pack, unpack, MsgType

log = logging.getLogger("transport")


class ReliableUDP(Transport):
    """UDP transport. Step 1: unreliable send/receive, broadcast, loss simulation."""

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

    # ---- interface ----
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
        raise NotImplementedError("added in step 2")

    # ---- internals ----
    def _send_raw(self, addr, data):
        if self.loss_rate and self.rng.random() < self.loss_rate:
            return
        try:
            self.sock.sendto(data, addr)
            self.stats["sent"] += 1
        except OSError as e:
            log.debug("[%s] send error: %s", self.my_id, e)

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
            self._on_packet(pkt, addr)

    def _on_packet(self, pkt, addr):
        if pkt.seq == 0 and not (pkt.flags & 0x01):
            self._dispatch(pkt.sender_id, addr, pkt.type, pkt.payload)

    def _dispatch(self, sender_id, addr, msg_type, payload):
        h = self.handlers.get(int(msg_type))
        if h is None:
            return
        try:
            h(sender_id, addr, int(msg_type), payload)
        except Exception:
            log.exception("[%s] handler error for type %s", self.my_id, msg_type)