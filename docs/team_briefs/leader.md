# ROLE: LEADER. Branch: feat/leader-transport
Folders: src/p2p/common/ (frozen contract, already done), src/p2p/transport/, src/p2p/node.py, src/p2p/cli.py, scripts/, results/, docs/report, plus reviewing all PRs.

## Task L1: ReliableUDP transport (Mon 23 and Tue 24) in src/p2p/transport/reliable_udp.py
`class ReliableUDP(Transport)`, constructor `ReliableUDP(my_id, port, loss_rate=0.0, bind_ip="0.0.0.0")`.
Implements protocol.md section 4 EXACTLY:
- One UDP socket for the peer's port (SO_REUSEADDR). A second socket bound to DISCOVERY_PORT 5000 (SO_REUSEADDR, and SO_REUSEPORT where available) used for receiving broadcast DISCOVER; its packets feed the same dispatcher. `broadcast()` sends from the main socket (SO_BROADCAST on) to 255.255.255.255 and port 5000. Ignore your own DISCOVER (sender_id == my_id).
- Random 1..255 `session` at start. Per remote address (ip, port) state: session, send_base, next_seq (starts 1), unacked{seq: (packet bytes, first_sent, last_sent, retries, retransmitted)}, send queue for packets beyond the window, recv_base (starts 1), recv_buf{seq: packet}, fragment buffer, SRTT, RTTVAR, RTO (initial 1 s).
- send_reliable: split payload into <=1024-byte fragments, each a reliable packet (flags RELIABLE, MORE_FRAG on all but last), same type, own seq. Max logical message 256 KiB (raise ValueError beyond). Respect window 32; extra packets wait in a queue; send_reliable never blocks the caller.
- Receiving reliable packet: send standalone ACK (type ACK, seq 0, header ack = recv_base after processing, payload = sack_base(u32)=ack+1, sack_bitmap(u32)) for EVERY reliable packet including duplicates. Buffer out-of-order inside [recv_base, recv_base+32), deliver in order, drop duplicates. Reassemble fragments: concatenate until a packet without MORE_FRAG, then call the handler once.
- Process the `ack` field and SACK of ACK packets: slide send_base, mark SACKed packets so they are not retransmitted. RTT sample only from never-retransmitted packets (Karn). RTO = SRTT + 4*RTTVAR clamped to [RTO_MIN, RTO_MAX]; double on timeout.
- Timer thread (every 20 ms): retransmit expired packets; after MAX_RETRIES (8) retransmissions call the unreachable callback once with the address and drop that peer's state.
- Session rule (4.6): packet from known address with a different session resets all state for that address.
- Unreliable (seq 0): delivered immediately, never ACKed. Handlers get `(sender_id, addr, msg_type, payload)`.
- `loss_rate` drops that fraction of outgoing AND incoming packets at random (for experiments; seedable). Also expose counters: packets sent, retransmitted, bytes delivered.
- Handlers are dispatched on the receiver thread; a handler exception must be logged, not kill the thread.
Tests (tests/test_transport.py, two ReliableUDP on 127.0.0.1): 1) 10 reliable messages arrive in order exactly once; 2) 200 KB message arrives intact (fragmentation); 3) with loss_rate=0.2 on both sides, 1 MB arrives intact; 4) duplicate injected packets are not delivered twice; 5) after stopping one side, the other calls the unreachable callback within ~30 s (shorten with a test config); 6) session change resets state; 7) ACK/SACK payload encode/decode round trip.

## Task L2: Node and CLI (Wed 25)
src/p2p/node.py: `Node(peer_id, port, name, bootstrap, data_dir, shared_dir, loss_rate=0.0)`; builds ReliableUDP, Membership, Chat, StorageManager, TransferService; wires them (see contracts below); `start()`, `stop()`, `leave()`.
src/p2p/cli.py (run as `python -m p2p.cli --id 1 --port 5001 [--bootstrap ip:port] [--name n] [--share path ...] [--loss 0.1]`): commands `/peers`, `/files`, `/share <path>`, `/download <name> [dest]`, `/msg <id> <text>`, `/chunks <name>` (show holders), `/stats`, `/quit`. Plain text = group chat. Print incoming chat as `[id name] text`.
Wiring contract (what Areesha and Hamza implement; you call it):
- `Membership(transport, my_id, my_port, name="", bootstrap=None)`; methods `start()`, `stop()`, `join()`, `leave()`, `alive_peers()`, `on_change(cb)`, `peer_name(id)`, `report_unreachable(addr)`; attributes `state_provider` (callable returning `(manifest_payloads: list[bytes], chunk_map: list[(fid: bytes, idx: int, holders: list[int])])`) and `state_consumer` (callable taking the same two values).
- `Chat(transport, membership, my_id, on_message)`; `on_message(sender_id, text, private: bool)`; methods `send(text)`, `send_private(peer_id, text)`.
- `StorageManager(data_dir, my_id)`; `export_state()` and `import_state(manifests, chunk_map)` match state_provider/state_consumer.
- `TransferService(transport, membership, storage, my_id)`; `share_file(path)`, `list_files()`, `download(name_or_fid_hex, dest_dir, progress_cb=None) -> str path`, `chunk_holders(name)`, `start()`, `stop()`.
Wire: `membership.state_provider = storage.export_state`; `membership.state_consumer = storage.import_state`; `transport.set_unreachable_handler(membership.report_unreachable)`.

## Task L3: Reviews and integration (Mon 23 to Thu 26)
Review every PR against protocol.md: payload offsets, constants, no sockets in services, tests present and passing. Merge into develop in this order: common fixes, transport, membership, storage, chat, transfer, node/cli.
Integration scripts in scripts/: `run_local.ps1` starts 4 peers on ports 5001-5004 (bootstrap 127.0.0.1:5001); `demo_kill.md` is the demo steps.

## Task L4: Experiments (Fri 27) in scripts/experiments.py, results to results/*.csv and results/graphs/*.png
1) Throughput of a 5 MB reliable transfer vs loss 0/5/10/20 % (3 runs each, mean). 2) Download time vs chunk size 16/64/256 KiB. 3) Failover time: seconds from killing a source to download completion. 4) Storage and bandwidth for R=2 vs R=3 (computed). 5) Chat latency while a download runs. Use matplotlib; every graph has axis labels, units and a caption.

## Task L5: Report and demo (Sat 28 to Sun 29)
Report (docs/report/report.md, export to PDF): protocol spec (from protocol.md), design and decisions, flow diagrams (join, chat, download, failure; draw in docs/diagrams/ as PNG), results and graphs, how to run. Merge develop into main only on Sun 29 after the demo works. Create the submission zip (code, report, run instructions, no .venv, no .bin).

## Definition of done (leader)
All transport tests pass at 0 and 20 % loss; 4 local peers run; kill during download demo works 5 times in a row; report and zip ready by Sun 29.