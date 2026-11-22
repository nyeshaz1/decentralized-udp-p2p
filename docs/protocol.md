# Protocol Specification, version 1 (FROZEN: changes only via leader)

All integers are big-endian (network byte order). Transport: UDP.

## 1. Header (fixed 24 bytes)
| Offset | Size | Field       | Description |
|-------:|-----:|-------------|-------------|
| 0  | 2 | magic       | 0x5032 |
| 2  | 1 | version     | 1 |
| 3  | 1 | type        | message type (section 2) |
| 4  | 1 | flags       | bit0 RELIABLE, bit1 ACK_ONLY, bit2 MORE_FRAG, bit3 ENCRYPTED |
| 5  | 1 | reserved    | 0 |
| 6  | 4 | sender_id   | uint32 peer id |
| 10 | 4 | seq         | per (sender -> receiver) transport sequence number |
| 14 | 4 | ack         | cumulative ACK: next seq expected from the peer |
| 18 | 2 | payload_len | bytes after the header (max 1024) |
| 20 | 4 | crc32       | CRC32 of header (crc field = 0) + payload |
Struct format: ">HBBBBIIIHI". Packets failing magic/version/CRC are dropped silently.

## 2. Message types
| Code | Name | Reliable | Purpose |
|-----:|------|:-------:|---------|
| 0x01 | DISCOVER       | no  | broadcast "who is there" |
| 0x02 | DISCOVER_REPLY | no  | peer announces ip, port, id |
| 0x03 | JOIN           | yes | join request (id, port) |
| 0x04 | JOIN_ACK       | yes | member list + file manifests + chunk map |
| 0x05 | MEMBER_UPDATE  | yes | gossip: peer joined/left/failed |
| 0x06 | LEAVE          | yes | graceful leave |
| 0x07 | HEARTBEAT      | no  | every 1 s; peer failed after 5 s silence |
| 0x10 | CHAT           | yes | payload: chat_seq(4) + utf-8 text |
| 0x11 | PRIVATE_MSG    | yes | one-to-one message (bonus) |
| 0x20 | ACK            | no  | transport ACK; payload = SACK bitmap (4 B base + 4 B bitmap) |
| 0x30 | FILE_MANIFEST  | yes | file name, size, chunk size, per-chunk SHA-256, file SHA-256 |
| 0x31 | CHUNK_STORE    | yes | push chunk to a replica holder |
| 0x32 | CHUNK_REQUEST  | yes | file_id(16) + chunk_index(4) |
| 0x33 | CHUNK_DATA     | yes | file_id + chunk_index + bytes (fragmented via MORE_FRAG) |
| 0x34 | CHUNK_ERROR    | yes | not-found / busy |
| 0x35 | REPLICA_UPDATE | yes | chunk location map changed (re-replication) |

## 3. Sequences
- **Join:** DISCOVER (broadcast) or bootstrap -> JOIN -> JOIN_ACK -> JOIN to all listed members -> receive chunk assignments via CHUNK_STORE.
- **Chat:** CHAT sent reliably to every peer; receiver dedups on (sender_id, chat_seq) and delivers in chat_seq order.
- **Leave:** LEAVE -> MEMBER_UPDATE -> re-replication of chunks it held.
- **Crash:** no HEARTBEAT for 5 s -> mark failed -> MEMBER_UPDATE -> re-replicate.
- **Download:** parallel CHUNK_REQUEST to >= 2 replicas -> CHUNK_DATA -> verify SHA-256; on timeout or peer failure retry on another replica.

## 4. Reliability rules
Selective Repeat, window 32 packets, SRTT/RTTVAR RTO (RFC 6298, min 200 ms, max 3 s), max 8 retransmits then peer is declared unreachable. Receiver buffers out-of-order packets, delivers in order, and discards duplicates.
