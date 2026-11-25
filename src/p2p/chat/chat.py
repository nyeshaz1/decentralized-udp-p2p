"""Group chat with per-sender ordering and duplicate suppression (Task A3).

Implements protocol.md section 6.3. The transport already gives ordered,
exactly-once delivery per peer pair, so the checks here are a second line of
defence (reordering, duplicates, reconnects).

Threading rules:
  * Handlers return fast. Deliveries are queued while the state lock is held
    (so the decision order is the delivery order) and handed to ``on_message``
    by one dispatcher thread, which holds no lock.
  * send() never holds the state lock while sending.
"""
import logging
import queue
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from p2p.chat import messages as cm
from p2p.common.interfaces import MembershipView, Transport
from p2p.common.protocol import MsgType

log = logging.getLogger("p2p.chat")

MAX_HELD = 1000   # buffered out-of-order messages per sender


@dataclass
class _SenderState:
    """Receive state for one sender in the current session."""
    expected: Optional[int] = None            # None until the first chat_seq is seen
    held: Dict[int, str] = field(default_factory=dict)   # {seq: text} (seq > expected)


class Chat:
    """Group chat: send to everyone, deliver each sender's messages in order."""

    def __init__(self, transport: Transport, membership: MembershipView, my_id: int,
                 on_message: Callable[[int, str, bool], None], max_buffer: int = MAX_HELD):
        """Create the service and register its handlers (no start() call needed).

        on_message(sender_id, text, private) is called outside every lock.
        """
        self.transport = transport
        self.membership = membership
        self.my_id = my_id
        self.on_message = on_message
        self.max_buffer = max_buffer

        self._lock = threading.Lock()          # protects _senders
        self._send_lock = threading.Lock()     # keeps seq assignment and sends in order
        self._next_seq = 1
        self._senders: Dict[int, _SenderState] = {}
        self._out: "queue.Queue" = queue.Queue()
        self._started = False
        self._thread: Optional[threading.Thread] = None
        self.start()

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        """Register handlers and start the delivery thread (idempotent)."""
        if self._started:
            return
        self._started = True
        self.transport.register_handler(MsgType.CHAT, self._on_chat)
        self.transport.register_handler(MsgType.PRIVATE_MSG, self._on_private)
        self.membership.on_change(self._on_member_change)
        self._thread = threading.Thread(target=self._deliver_loop,
                                        name=f"chat-deliver-{self.my_id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the delivery thread (safe to call more than once)."""
        self._out.put(None)
        if self._thread is not None and self._thread.is_alive() \
                and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)

    # --------------------------------------------------------------- sending
    def send(self, text: str) -> int:
        """Send a group message to every alive peer; return its chat_seq.

        Raises ValueError if the text is over 1000 UTF-8 bytes (no seq is used).
        """
        with self._send_lock:
            cm.encode_chat(0, text)                  # validate length before taking a seq
            seq = self._next_seq
            self._next_seq += 1
            payload = cm.encode_chat(seq, text)
            targets = self.membership.alive_peers()
            for peer_id, addr in targets.items():
                self._send(addr, MsgType.CHAT, payload)
        log.debug("[peer %d] CHAT seq=%d sent to %d peers", self.my_id, seq, len(targets))
        return seq

    def send_private(self, peer_id: int, text: str) -> None:
        """Send a private message to one alive peer.

        Raises ValueError for an over-long text or a peer that is not alive.
        """
        payload = cm.encode_private(text)
        addr = self.membership.alive_peers().get(peer_id)
        if addr is None:
            raise ValueError(f"peer {peer_id} is not alive")
        self._send(addr, MsgType.PRIVATE_MSG, payload)

    def _send(self, addr, msg_type: int, payload: bytes) -> None:
        """Reliable send that never raises."""
        try:
            self.transport.send_reliable(addr, msg_type, payload)
        except Exception:
            log.exception("[peer %d] send to %s failed", self.my_id, addr)

    # ------------------------------------------------------------- receiving
    def _on_chat(self, sender_id, addr, msg_type, payload) -> None:
        """CHAT: drop duplicates, buffer gaps, deliver consecutive messages in order."""
        if sender_id == self.my_id:
            return
        try:
            seq, text = cm.decode_chat(payload)
        except ValueError:
            log.warning("[peer %d] bad CHAT from peer %d dropped", self.my_id, sender_id)
            return
        with self._lock:
            st = self._senders.setdefault(sender_id, _SenderState())
            if st.expected is None:
                st.expected = seq                    # session starts at the first seq seen
            if seq < st.expected:
                log.debug("[peer %d] duplicate CHAT %d from %d dropped", self.my_id, seq, sender_id)
                return
            if seq > st.expected:
                if seq in st.held:
                    return                           # duplicate of a buffered message
                if len(st.held) >= self.max_buffer:
                    log.warning("[peer %d] buffer full for sender %d, CHAT %d dropped",
                                self.my_id, sender_id, seq)
                    return
                st.held[seq] = text
                return
            self._out.put((sender_id, text, False))
            st.expected += 1
            while st.expected in st.held:            # flush consecutive buffered messages
                self._out.put((sender_id, st.held.pop(st.expected), False))
                st.expected += 1

    def _on_private(self, sender_id, addr, msg_type, payload) -> None:
        """PRIVATE_MSG: deliver straight away (the transport already orders it)."""
        if sender_id == self.my_id:
            return
        try:
            text = cm.decode_private(payload)
        except ValueError:
            log.warning("[peer %d] bad PRIVATE_MSG from peer %d dropped", self.my_id, sender_id)
            return
        self._out.put((sender_id, text, True))

    def _on_member_change(self, event: str, peer_id: int) -> None:
        """Forget a sender's session when it leaves or fails (a rejoin starts fresh)."""
        if event in ("leave", "fail"):
            with self._lock:
                self._senders.pop(peer_id, None)

    def _deliver_loop(self) -> None:
        """Hand queued messages to on_message one at a time, outside every lock."""
        while True:
            item = self._out.get()
            if item is None:
                return
            try:
                self.on_message(*item)
            except Exception:
                log.exception("[peer %d] on_message callback failed", self.my_id)
