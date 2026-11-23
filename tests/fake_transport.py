import queue, random, threading, traceback
from p2p.common.interfaces import Transport


class FakeNetwork:
    def __init__(self, loss=0.0, dup=0.0, seed=1):
        self.nodes = {}
        self.loss, self.dup = loss, dup          # apply to unreliable sends only
        self.rng = random.Random(seed)

    def create(self, peer_id, port, ip="127.0.0.1"):
        t = FakeTransport(self, peer_id, (ip, port))
        self.nodes[(ip, port)] = t
        return t

    def _deliver(self, src, dst, msg_type, payload, reliable):
        if src.dead:
            return
        node = self.nodes.get(dst)
        if node is None or node.dead:
            if reliable and src._unreachable_cb:
                threading.Timer(2.0, src._unreachable_cb, [dst]).start()
            return
        copies = 1
        if not reliable:
            if self.rng.random() < self.loss:
                return
            if self.rng.random() < self.dup:
                copies = 2
        for _ in range(copies):
            node.inbox.put((src.peer_id, src.addr, int(msg_type), payload))


class FakeTransport(Transport):
    def __init__(self, net, peer_id, addr):
        self.net, self.peer_id, self.addr = net, peer_id, addr
        self.handlers, self.inbox = {}, queue.Queue()
        self.dead, self._running, self._thread = False, False, None
        self._unreachable_cb = None

    def send_reliable(self, addr, msg_type, payload):
        self.net._deliver(self, tuple(addr), msg_type, payload, True)

    def send_unreliable(self, addr, msg_type, payload):
        self.net._deliver(self, tuple(addr), msg_type, payload, False)

    def broadcast(self, msg_type, payload, port):
        for a, node in list(self.net.nodes.items()):
            if node is not self:
                self.net._deliver(self, a, msg_type, payload, False)

    def register_handler(self, msg_type, handler):
        self.handlers[int(msg_type)] = handler

    def set_unreachable_handler(self, cb):
        self._unreachable_cb = cb

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running:
            try:
                item = self.inbox.get(timeout=0.1)
            except queue.Empty:
                continue
            if self.dead:
                continue
            h = self.handlers.get(item[2])
            if h:
                try:
                    h(*item)
                except Exception:
                    traceback.print_exc()

    def stop(self):
        self._running = False

    def kill(self):
        """Simulate a crash: stops sending and receiving, no LEAVE."""
        self.dead = True
        self._running = False


