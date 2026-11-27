import time
from p2p.node import Node


def wait_until(cond, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_two_nodes_chat():
    got = []
    n1 = Node(1, 48001, name="a", data_dir="node_data/t1")
    n2 = Node(2, 48002, name="b", bootstrap=("127.0.0.1", 48001),
              data_dir="node_data/t2",
              on_message=lambda sid, text, priv: got.append((sid, text, priv)))
    try:
        n1.start()
        n2.start()
        assert wait_until(lambda: 2 in n1.membership.alive_peers()
                          and 1 in n2.membership.alive_peers())
        n1.chat.send("hello")
        assert wait_until(lambda: (1, "hello", False) in got)
    finally:
        n2.stop()
        n1.stop()