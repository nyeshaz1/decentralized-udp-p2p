import logging
import os

from p2p.transport.reliable_udp import ReliableUDP
from p2p.membership.membership import Membership, MembershipError
from p2p.chat.chat import Chat

try:  # Hamza's modules: optional until his PR is merged
    from p2p.storage.manager import StorageManager
    from p2p.transfer.transfer import TransferService
except ImportError:
    StorageManager = TransferService = None

log = logging.getLogger("node")

__all__ = ["Node", "MembershipError"]


class Node:
    """Wires transport, membership, chat, storage and transfer into one peer."""

    def __init__(self, peer_id, port, name="", bootstrap=None,
                 data_dir=None, shared_dir="shared_files", loss_rate=0.0,
                 on_message=None):
        self.peer_id = peer_id
        self.port = port
        self.name = name or f"peer{peer_id}"
        self.shared_dir = shared_dir
        self.data_dir = data_dir or os.path.join("node_data", str(peer_id))
        os.makedirs(self.data_dir, exist_ok=True)
        self._on_message = on_message or (lambda sid, text, private: None)

        self.transport = ReliableUDP(peer_id, port, loss_rate=loss_rate)
        self.membership = Membership(self.transport, peer_id, port,
                                     name=self.name, bootstrap=bootstrap)
        self.chat = Chat(self.transport, self.membership, peer_id,
                         self._deliver)

        self.storage = None
        self.transfer = None
        if StorageManager is not None and TransferService is not None:
            self.storage = StorageManager(self.data_dir, peer_id)
            self.transfer = TransferService(self.transport, self.membership,
                                            self.storage, peer_id)
            self.membership.state_provider = self.storage.export_state
            self.membership.state_consumer = self.storage.import_state

        self.transport.set_unreachable_handler(self.membership.report_unreachable)

    @property
    def has_files(self):
        return self.transfer is not None

    def _deliver(self, sender_id, text, private):
        self._on_message(sender_id, text, private)

    def start(self):
        """Start all services and join the group. Raises MembershipError."""
        self.membership.start()
        if hasattr(self.chat, "start"):
            self.chat.start()
        if self.transfer is not None:
            self.transfer.start()
        self.transport.start()
        self.membership.join()
        log.info("[%s] node started on port %s", self.peer_id, self.port)

    def leave(self):
        """Graceful leave: tell the others, then stop."""
        try:
            self.membership.leave()
        finally:
            self.stop()

    def stop(self):
        """Stop everything without announcing (also used after leave)."""
        for svc in (self.transfer, self.chat, self.membership):
            if svc is not None and hasattr(svc, "stop"):
                try:
                    svc.stop()
                except Exception:
                    log.exception("[%s] error stopping %s", self.peer_id, svc)
        self.transport.stop()

    def stats(self):
        return dict(self.transport.stats)