"""CONTRACT between modules. Changes only via leader."""
from abc import ABC, abstractmethod
from typing import Callable, Tuple, Optional

Addr = Tuple[str, int]
# handler(sender_id, addr, msg_type, payload)
Handler = Callable[[int, Addr, int, bytes], None]

class Transport(ABC):
    @abstractmethod
    def send_reliable(self, addr: Addr, msg_type: int, payload: bytes) -> None:
        """Ordered, exactly-once delivery to addr (fragments automatically)."""
    @abstractmethod
    def send_unreliable(self, addr: Addr, msg_type: int, payload: bytes) -> None: ...
    @abstractmethod
    def broadcast(self, msg_type: int, payload: bytes, port: int) -> None: ...
    @abstractmethod
    def register_handler(self, msg_type: int, handler: Handler) -> None: ...
    @abstractmethod
    def start(self) -> None: ...
    @abstractmethod
    def stop(self) -> None: ...
    def set_unreachable_handler(self, cb) -> None:
        """cb(addr) is called when a peer exceeds MAX_RETRIES (treated as FAILED)."""
        self._unreachable_cb = cb

class MembershipView(ABC):
    """Implemented by membership/ (Areesha), used by storage/transfer (Hamza)."""
    @abstractmethod
    def alive_peers(self) -> dict:  # {peer_id: (ip, port)}
        ...
    @abstractmethod
    def on_change(self, callback: Callable[[str, int], None]) -> None:
        """callback(event, peer_id), event in {'join','leave','fail'}"""
