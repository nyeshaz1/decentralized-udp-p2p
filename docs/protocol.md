# Protocol Specification, version 1.1 (FROZEN: changes only via leader)

Transport: UDP. All integers are big-endian (network byte order).
A peer written by anyone who follows this document exactly must interoperate with ours.

## 0. Notation
| Name | Encoding |
|---|---|
| u8, u16, u32, u64 | unsigned integer, 1/2/4/8 bytes, big-endian |
| ip4 | 4 bytes, IPv4 address in network order |
| str8 | u8 length N (0..255) followed by N bytes of UTF-8 |
| fid | 16 bytes: file_id = first 16 bytes of the file's SHA-256 |
| h32 | 32 bytes: SHA-256 digest |

## 1. Header (fixed 24 bytes)
| Offset | Size | Field | Description |
|-------:|-----:|-------|-------------|
| 0  | 2 | magic       | 0x5032 |
| 2  | 1 | version     | 1 |
| 3  | 1 | type        | message type (section 2) |
| 4  | 1 | flags       | bit0 RELIABLE, bit2 MORE_FRAG. bit1 and bit3 are reserved (send 0, ignore on receive) |
| 5  | 1 | session     | 1..255, chosen randomly when a peer process starts (section 4.6) |
| 6  | 4 | sender_id   | uint32 peer id, unique in the group |
| 10 | 4 | seq         | transport sequence number. Reliable packets: 1, 2, 3, ... per (sender, receiver). Unreliable packets: 0 |
| 14 | 4 | ack         | cumulative ACK: next seq the sender of this packet expects from the receiver. 0 if not meaningful |
| 18 | 2 | payload_len | bytes after the header, 0..1024 |
| 20 | 4 | crc32       | CRC32 over header (crc field set to 0) + payload |

Struct format: `">HBBBBIIIHI"`. A packet that fails magic, version, length or CRC is dropped silently.
A packet with an unknown `type` is ignored (but still ACKed if RELIABLE).

## 2. Message types
| Code | Name | Reliable | Purpose |
|-----:|------|:--:|---------|
| 0x01 | DISCOVER       | no  | LAN broadcast: "who is there" |
| 0x02 | DISCOVER_REPLY | no  | unicast answer to DISCOVER |
| 0x03 | JOIN           | yes | join request, also sent to every member after joining |
| 0x04 | JOIN_ACK       | yes | members + manifests + chunk map |
| 0x05 | MEMBER_UPDATE  | yes | gossip: peer joined or failed |
| 0x06 | LEAVE          | yes | graceful leave |
| 0x07 | HEARTBEAT      | no  | liveness, every 1 s |
| 0x10 | CHAT           | yes | group chat message |
| 0x11 | PRIVATE_MSG    | yes | one-to-one message (stretch) |
| 0x20 | ACK            | no  | transport acknowledgement with SACK |
| 0x30 | FILE_MANIFEST  | yes | description of one shared file |
| 0x31 | CHUNK_STORE    | yes | push one chunk to a replica holder |
| 0x32 | CHUNK_REQUEST  | yes | ask a holder for one chunk |
| 0x33 | CHUNK_DATA     | yes | chunk bytes |
| 0x34 | CHUNK_ERROR    | yes | chunk cannot be served |
| 0x35 | REPLICA_UPDATE | yes | a peer now holds or no longer holds a chunk |

## 3. Payload layouts
Offsets are inside the logical payload (after reassembly, section 4.4). The logical payload of one message is at most 256 KiB.

**DISCOVER (0x01)**
| Field | Type | Note |
|---|---|---|
| port | u16 | UDP port the sender listens on (also its source port) |

Sent to the broadcast address, port 5000 (`DISCOVERY_PORT`). Every peer binds port 5000 with SO_REUSEADDR in addition to its own port, and ignores its own DISCOVER.

**DISCOVER_REPLY (0x02)**
| Field | Type | Note |
|---|---|---|
| port | u16 | replier's listening port |

Sent unicast to the DISCOVER source IP and the `port` in DISCOVER. The replier's IP is the packet source IP. A peer ignores DISCOVER_REPLY from itself.

**JOIN (0x03)**
| Field | Type | Note |
|---|---|---|
| port | u16 | listening port |
| name | str8 | display name, may be empty |

**JOIN_ACK (0x04)**
| Field | Type | Note |
|---|---|---|
| status | u8 | 0 = OK, 1 = ID_IN_USE (rest of payload is absent) |
| n_members | u16 | |
| members[n] | (u32 peer_id, ip4, u16 port, str8 name) | alive members, including the replier |
| n_files | u16 | |
| manifests[n] | (u32 length, FILE_MANIFEST payload) | |
| n_entries | u32 | |
| chunk_map[n] | (fid, u32 idx, u8 n_holders, u32 holder_id x n_holders) | actual holders |

**MEMBER_UPDATE (0x05)**
| Field | Type | Note |
|---|---|---|
| event | u8 | 1 = JOINED, 3 = FAILED (2 is unused, graceful leave uses LEAVE) |
| peer_id | u32 | |
| ip | ip4 | zeros for FAILED |
| port | u16 | zero for FAILED |

**LEAVE (0x06)**: empty payload.

**HEARTBEAT (0x07)**
| Field | Type | Note |
|---|---|---|
| tick | u32 | counter incremented per heartbeat (debugging only) |

**CHAT (0x10)**
| Field | Type | Note |
|---|---|---|
| chat_seq | u32 | per sender, starts at 1, +1 per message |
| text | UTF-8 | rest of payload, at most 1000 bytes |

**PRIVATE_MSG (0x11)**: payload is UTF-8 text (at most 1000 bytes), sent only to the target peer.

**ACK (0x20)** (header `ack` = cumulative ACK, seq = 0)
| Field | Type | Note |
|---|---|---|
| sack_base | u32 | = ack + 1 |
| sack_bitmap | u32 | bit i (LSB = bit 0) set means seq `sack_base + i` was received out of order |

**FILE_MANIFEST (0x30)**
| Field | Type | Note |
|---|---|---|
| file_id | fid | first 16 bytes of file_hash |
| size | u64 | file size in bytes |
| chunk_size | u32 | 65536 (last chunk may be shorter) |
| n_chunks | u32 | ceil(size / chunk_size) |
| file_hash | h32 | SHA-256 of the whole file |
| name | str8 | file name, no path |
| chunk_hashes | h32 x n_chunks | SHA-256 of each chunk, in index order |

**CHUNK_STORE (0x31)** and **CHUNK_DATA (0x33)** (identical layout)
| Field | Type | Note |
|---|---|---|
| file_id | fid | |
| idx | u32 | chunk index from 0 |
| data_len | u32 | equals chunk length |
| data | bytes | |

**CHUNK_REQUEST (0x32)**: file_id (fid) + idx (u32).

**CHUNK_ERROR (0x34)**: file_id (fid) + idx (u32) + code (u8): 1 = NOT_FOUND, 2 = BUSY, 3 = UNKNOWN_FILE.

**REPLICA_UPDATE (0x35)**
| Field | Type | Note |
|---|---|---|
| file_id | fid | |
| idx | u32 | |
| action | u8 | 1 = ADD (holder now stores it), 2 = REMOVE |
| holder_id | u32 | |

## 4. Transport rules (Selective Repeat, no congestion control)
**4.1 Addressing.** Every peer sends all packets from the same UDP socket it listens on. Per-peer transport state is keyed by the remote address (ip, port). `sender_id` in the header is passed to handlers.

**4.2 Sequence numbers.** Reliable packets carry `seq` starting at 1 per (sender, receiver) pair. Unreliable packets (DISCOVER, DISCOVER_REPLY, HEARTBEAT, ACK) carry `seq = 0`, are never ACKed, never retransmitted and are delivered immediately.

**4.3 ACKs.** For every reliable packet received (including duplicates and out-of-window packets below the window) the receiver sends a standalone ACK carrying the cumulative `ack` (next expected seq) and the SACK bitmap. Reliable data packets may also carry the current cumulative `ack` for the reverse direction (piggyback); a receiver processes the `ack` field of every reliable packet.

**4.4 Fragmentation.** A logical message larger than 1024 bytes is split into fragments of at most 1024 bytes. Each fragment is its own reliable packet with its own `seq`, the same `type`, and MORE_FRAG set on all but the last. Because reliable delivery is in order, the receiver concatenates payloads until it sees a packet without MORE_FRAG, then delivers one logical message to the handler. Example: a 65560-byte CHUNK_DATA payload (64 KiB chunk + 24-byte prefix) becomes 65 fragments.

**4.5 Window and timers.**
- Window: 32 packets. The sender may have seqs `[send_base, send_base + 32)` outstanding; `send_base` = lowest unACKed seq.
- Receiver accepts seqs `[recv_base, recv_base + 32)`, buffers out-of-order, delivers in order, drops duplicates. Seqs outside the window are dropped (but ACKed if below `recv_base`).
- A packet covered by SACK is not retransmitted.
- RTO per RFC 6298: initial 1 s, SRTT/RTTVAR updated only from packets never retransmitted (Karn), RTO clamped to [0.2 s, 3 s], doubled on every timeout.
- After 8 retransmissions of one packet the peer is reported unreachable (treated as FAILED).

**4.6 Sessions.** `session` identifies one run of a peer process. If a packet arrives from a known address with a different `session` than recorded, the receiver discards all transport state for that address (send and receive) and adopts the new session. This lets a crashed peer rejoin with the same id and port and restart `seq` at 1.

## 5. Membership rules
- `peer_id` is chosen by the user (`--id`) and must be unique. If a JOIN arrives with an id already used by an alive member at a different address, reply JOIN_ACK status = 1; the joiner exits with an error.
- **Liveness:** any valid packet from a peer refreshes its `last_seen`. HEARTBEAT is sent unreliably to every alive peer every 1.0 s (`HEARTBEAT_INTERVAL`).
- **Failure:** a peer is FAILED after 5.0 s (`PEER_TIMEOUT`) without any packet, or when the transport reports it unreachable. The detector sends MEMBER_UPDATE (FAILED) to all other alive peers. Receivers that already consider the peer failed ignore it. Gossip is not forwarded (full mesh), so processing is idempotent.
- **Leave:** LEAVE is sent reliably to every alive peer, then the peer waits up to 1 s for ACKs and stops. Receivers remove it at once.
- **Rejoin:** a peer previously marked FAILED or LEFT that sends a valid JOIN is treated as a new join.

## 6. Sequences
**6.1 Join**
1. Joiner J sends DISCOVER (broadcast) or, with `--bootstrap`, sends JOIN straight to the bootstrap address.
2. Member M answers DISCOVER_REPLY (unicast). J sends JOIN to M (retry DISCOVER every 2 s, up to 3 times, then run alone).
3. M adds J, replies JOIN_ACK (members, manifests, chunk map), and sends MEMBER_UPDATE (JOINED) to the other members.
4. J sends JOIN to every other member in the JOIN_ACK list. They add J and answer JOIN_ACK (J ignores their lists except to merge unknown manifests and map entries). The bootstrap is no longer needed.
5. Chunk handover (6.2) starts.

**6.2 Chunk placement and handover**
- Placement function (all peers compute it identically): for peer p, file_id f and chunk idx i, score = first 8 bytes (big-endian u64) of SHA-256(`f` + `i` as u32 + `p` as u32). Holders are the R = 2 alive peers with the highest scores; ties go to the lower peer_id.
- **Sharing a file** (needs at least 3 alive peers so no peer holds all chunks): the seeder splits the file, builds the manifest, sends FILE_MANIFEST to all peers, then CHUNK_STORE for each chunk to each of its 2 holders (if the holder is the seeder, store locally). A holder verifies the chunk SHA-256 against the manifest, writes it to disk, and sends REPLICA_UPDATE (ADD) to all peers. The seeder deletes any chunk it does not hold per placement.
- **Join handover:** when J joins, every peer recomputes placement. For each chunk where J is now a holder and does not hold it, the current holder with the lowest peer_id sends CHUNK_STORE to J. After J's REPLICA_UPDATE (ADD), a former holder that is no longer in the top 2 deletes the chunk and sends REPLICA_UPDATE (REMOVE).
- **Re-replication (stretch):** when a peer leaves or fails, for every chunk with fewer than 2 alive holders, the alive holder with the lowest peer_id sends CHUNK_STORE to the new top-2 peer that lacks it.

**6.3 Chat**
1. Sender increments `chat_seq` and sends CHAT reliably to every alive peer, including peers that joined later (they only see new messages).
2. Receiver keeps `expected[sender]` (starts at the first chat_seq it sees from that sender in the current session). `chat_seq < expected`: drop (duplicate). `== expected`: deliver, increment, then deliver any buffered consecutive messages. `> expected`: buffer.
3. Because the transport is already ordered and exactly-once, these checks are a second line of defence (for example after reconnect).

**6.4 Download**
1. Downloader D has the manifest (from JOIN_ACK or FILE_MANIFEST) and the chunk map.
2. For each missing chunk, D picks one of its alive holders (alternating, so at least 2 peers serve in parallel) and sends CHUNK_REQUEST. At most 4 requests are outstanding per peer.
3. The holder replies CHUNK_DATA, or CHUNK_ERROR if it cannot (NOT_FOUND, UNKNOWN_FILE, BUSY).
4. D verifies SHA-256 against `chunk_hashes[idx]`. On mismatch, CHUNK_ERROR or no reply within 5 s, D retries the chunk on another holder. A chunk is retried at most 3 times per holder before the download reports failure.
5. When all chunks are present, D concatenates them and verifies `file_hash`.

**6.5 Failure during download**
1. Holder H dies. D gets a FAILED event (heartbeat timeout, MEMBER_UPDATE, or transport unreachable) or its request times out.
2. D removes H from all holder lists and re-requests the chunks that were outstanding or assigned to H from the other holder.
3. If no alive holder remains for a chunk, the download fails with a clear error.

## 7. Constants
| Name | Value |
|---|---|
| DISCOVERY_PORT | 5000 |
| HEARTBEAT_INTERVAL | 1.0 s |
| PEER_TIMEOUT | 5.0 s |
| CHUNK_SIZE | 65536 bytes |
| MAX_PAYLOAD per datagram | 1024 bytes |
| MAX logical message | 256 KiB |
| REPLICATION R | 2 |
| WINDOW | 32 packets |
| RTO | initial 1 s, min 0.2 s, max 3 s |
| MAX_RETRIES | 8 |
| Chunk request timeout | 5 s |

## 8. Version rules
`version` is 1. A packet with another version is dropped. Changes to this document are made only by the leader and bump the minor number; changes that alter byte layouts bump `version`.