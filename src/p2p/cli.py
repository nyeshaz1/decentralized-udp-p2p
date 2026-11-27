import argparse
import logging
import sys

from p2p.node import Node, MembershipError


def parse_addr(s):
    ip, port = s.rsplit(":", 1)
    return ip, int(port)


def main(argv=None):
    ap = argparse.ArgumentParser(description="UDP P2P chat and file sharing")
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--bootstrap", type=parse_addr, default=None, help="ip:port")
    ap.add_argument("--name", default="")
    ap.add_argument("--share", nargs="*", default=[], help="files to share")
    ap.add_argument("--loss", type=float, default=0.0)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    def on_message(sid, text, private):
        tag = "(private) " if private else ""
        name = node.membership.peer_name(sid) if "node" in globals() or True else ""
        print(f"\n[{sid} {name}] {tag}{text}")

    node = Node(args.id, args.port, name=args.name, bootstrap=args.bootstrap,
                loss_rate=args.loss, on_message=on_message)
    try:
        node.start()
    except MembershipError as e:
        print(f"Cannot join: {e}")
        node.stop()
        return 1

    print(f"Peer {args.id} on port {args.port}. Type text to chat, /help for commands.")
    for path in args.share:
        _cmd_share(node, path)

    try:
        while True:
            line = input("> ").strip()
            if not line:
                continue
            if line.startswith("/"):
                if not handle_command(node, line):
                    break
            else:
                try:
                    node.chat.send(line)
                except Exception as e:
                    print(f"send failed: {e}")
    except (EOFError, KeyboardInterrupt):
        pass
    node.leave()
    return 0


def _need_files(node):
    if not node.has_files:
        print("File sharing is not available in this build.")
        return False
    return True


def _cmd_share(node, path):
    if _need_files(node):
        try:
            node.transfer.share_file(path)
            print(f"shared {path}")
        except Exception as e:
            print(f"share failed: {e}")


def handle_command(node, line):
    """Return False to quit."""
    parts = line.split(maxsplit=2)
    cmd = parts[0]
    if cmd == "/quit":
        return False
    if cmd == "/help":
        print("/peers /files /share <path> /download <name> [dest] "
              "/msg <id> <text> /chunks <name> /stats /quit")
    elif cmd == "/peers":
        peers = node.membership.alive_peers()
        if not peers:
            print("no other peers")
        for pid, addr in sorted(peers.items()):
            print(f"  {pid} {node.membership.peer_name(pid)} {addr[0]}:{addr[1]}")
    elif cmd == "/msg" and len(parts) == 3:
        try:
            node.chat.send_private(int(parts[1]), parts[2])
        except Exception as e:
            print(f"msg failed: {e}")
    elif cmd == "/stats":
        print(node.stats())
    elif cmd == "/share" and len(parts) >= 2:
        _cmd_share(node, line.split(maxsplit=1)[1])
    elif cmd == "/files" and _need_files(node):
        for f in node.transfer.list_files():
            print(" ", f)
    elif cmd == "/download" and len(parts) >= 2 and _need_files(node):
        dest = parts[2] if len(parts) == 3 else "downloads"
        try:
            path = node.transfer.download(
                parts[1], dest,
                progress_cb=lambda d, t: print(f"\r  {d}/{t} chunks", end="", flush=True))
            print(f"\nsaved to {path}")
        except Exception as e:
            print(f"\ndownload failed: {e}")
    elif cmd == "/chunks" and len(parts) >= 2 and _need_files(node):
        print(node.transfer.chunk_holders(parts[1]))
    else:
        print("unknown command, try /help")
    return True


if __name__ == "__main__":
    sys.exit(main())