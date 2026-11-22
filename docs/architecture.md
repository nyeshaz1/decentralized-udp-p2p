# Architecture

## 1. Goals
Serverless group chat and distributed file storage over UDP, for 4+ peers.
No central server, no central storage. Every peer is both client and server.
Reliability is built above UDP (Selective Repeat, no congestion control).

## 2. Layered design
```
+---------------------------------------------------------+
| CLI (cli.py)        /chat /peers /files /download /quit |
+---------------------------------------------------------+
| Node (node.py)      builds services, dispatches by type |
+-----------+-----------+-----------+---------------------+
| membership| chat      | storage   | transfer            |
| (Areesha) | (Areesha) | (Hamza)   | (Hamza)             |
+-----------+-----------+-----------+---------------------+
| Reliable transport  transport/reliable_udp.py  (Leader) |
+---------------------------------------------------------+
| Codec               common/protocol.py (24 B header)    |
+---------------------------------------------------------+
| UDP socket (one per peer, plus broadcast on port 5000)  |
+---------------------------------------------------------+
```
Rules:
- A layer calls only the layer directly below it.
- Services never touch sockets. They use the `Transport` interface in `common/interfaces.py`.
- Services talk to each other only through `MembershipView` and callbacks.

## 3. Modules, owners, dependencies
| Module | Owner | Responsibility | Depends on |
|---|---|---|---|
| common/ | Leader | header codec, config constants, interfaces | none |
| transport/ | Leader | seq numbers, ACK/SACK, RTO, retransmit, fragmentation and reassembly, loss simulator | common |
| node.py | Leader | creates Transport and services, registers handlers, startup and shutdown | all |
| cli.py | Leader | command line and argument parsing | node |
| membership/ | Areesha | broadcast discovery, bootstrap join, heartbeat, failure detector, gossip | Transport |
| chat/ | Areesha | chat_seq, dedup, ordered delivery, private messages (stretch) | Transport, MembershipView |
| storage/ | Hamza | chunker, manifests, SHA-256, HRW placement, on-disk chunk store | MembershipView |
| transfer/ | Hamza | CHUNK_* handlers, parallel multi-source download, failover, re-replication (stretch) | Transport, storage, MembershipView |

## 4. Interfaces (the contract)
- `Transport`: `send_reliable`, `send_unreliable`, `broadcast`, `register_handler`, `start`, `stop`.
- `MembershipView`: `alive_peers() -> {id: (ip, port)}`, `on_change(callback(event, peer_id))` with event in `join | leave | fail`.
- Handler signature: `handler(sender_id, addr, msg_type, payload)`.
Fake in-memory transport (`tests/fake_transport.py`) implements `Transport`, so Areesha and Hamza test without the real network.

## 5. Core data structures
| Structure | Where | Shape |
|---|---|---|
| Peer table | membership | `{peer_id: PeerInfo(ip, port, last_seen, state)}` under a lock |
| Per-peer transport state | transport | `send_base, next_seq, unacked{seq: (pkt, sent_at, retries)}, recv_base, recv_buf{seq: pkt}, srtt, rttvar, rto, frag_buf` |
| Manifest | storage | `file_id(16 B), name, size, chunk_size, n_chunks, chunk_hashes[], file_hash` |
| Chunk map | storage | `{(file_id, idx): [peer_id, peer_id]}`, derived with HRW from the alive set |
| Chat state | chat | `next_chat_seq` (own), `expected[sender]`, `held[sender]{seq: text}` |
| Download state | transfer | `pending chunks, in_flight{idx: (peer, deadline)}, done{idx}, failed_peers` |

## 6. Concurrency model
- 1 receiver thread: reads the socket, decodes, dispatches to handlers.
- 1 timer thread: retransmit timers, heartbeats every 1 s, failure check.
- N download workers (4-8): fetch chunks in parallel.
- 1 CLI thread: user input.
- Locks: one per peer table, per transport peer-state, per chunk store. Handlers must return fast and push slow work (disk, hashing, downloads) to workers.

## 7. Storage layout on disk
```
node_data/<id>/chunks/<file_id_hex>_<idx>.chunk
node_data/<id>/manifests/<file_id_hex>.json
downloads/<id>/<filename>
shared_files/            source files (>= 2 MB) used to seed the group
```
No peer stores a full file. A seeding peer splits the file, keeps only the chunks HRW assigns to it, and pushes the rest with CHUNK_STORE.

## 8. Key flows
**Join**
1. New peer sends DISCOVER (broadcast) or contacts `--bootstrap ip:port`.
2. A member replies (DISCOVER_REPLY) and the new peer sends JOIN.
3. JOIN_ACK returns the member list, file manifests and chunk map.
4. The new peer sends JOIN to every listed member, and the bootstrap is no longer needed.
5. HRW is recomputed with the new peer, and the peers that hold chunks it now owns send them with CHUNK_STORE.

**Chat**
1. Sender increments `chat_seq` and sends CHAT reliably to every alive peer.
2. Receiver ignores `chat_seq < expected`, buffers `chat_seq > expected`, and delivers consecutive messages in order.

**Download (multi-source)**
1. Look up the manifest and the chunk map.
2. For each chunk, pick one of its 2 replicas (alternating, so at least 2 peers serve in parallel).
3. Send CHUNK_REQUEST. The holder replies with CHUNK_DATA (fragmented).
4. Verify the chunk SHA-256. If it is bad or times out, retry on the other replica.
5. When all chunks are done, assemble the file and verify the file hash.

**Failure during download**
1. The serving peer dies. Its in-flight requests time out and the downloader also gets a `fail` event from membership.
2. The downloader marks that peer failed and re-requests its chunks from the remaining replica.
3. The download completes without restarting.

**Crash or leave**
1. Leave: LEAVE is sent. Crash: no heartbeat for 5 s.
2. MEMBER_UPDATE is gossiped reliably.
3. Every peer recomputes HRW. Chunks that fall below 2 copies are re-replicated (stretch).

## 9. Failure model
| Event | Detected by | Reaction |
|---|---|---|
| Packet loss | missing ACK, RTO expiry | retransmit, max 8 times |
| Duplicate or reordered packet | seq number | drop duplicate, buffer out-of-order |
| Corrupt packet | CRC32 | drop silently |
| Corrupt chunk | SHA-256 | re-fetch from another replica |
| Peer crash | 5 s heartbeat silence or 8 failed retransmits | mark failed, gossip, failover |
| Network partition | not handled | out of scope |

## 10. Testing strategy
| Level | Tool | Example |
|---|---|---|
| Unit | pytest | codec round trip, HRW determinism, chunk hash check |
| Component (fake transport) | pytest | chat order with reordered and duplicated messages, membership timeouts |
| Transport under loss | built-in loss simulator (0/5/10/20 %) | 5 MB transfer completes and hash matches |
| Integration | scripts, 4 local peers on different ports | kill one peer mid-download, file still completes |
| Demo | 2-3 laptops on a hotspot | same scenario, live |

## 11. Experiments for the report
Throughput vs loss (0/5/10/20 %), chunk size (16/64/256 KiB) vs download time, failover time after a peer is killed, replication R=2 vs R=3 in storage and bandwidth, and chat latency while a download runs.

## 12. Out of scope
Congestion control, encryption (stretch, skipped), NAT traversal, persistence of chat history.