
# Application-Layer Protocol Specification

**Project:** Decentralized UDP-Based P2P Communication System  
**Protocol Name:** P2P Communication Protocol (P2P-UDP)  
**Protocol Version:** 1.0  
**Transport Protocol:** UDP  
**Byte Order:** Big-endian (Network Byte Order)  
**Status:** Initial Design

---

## 1. Introduction

P2P-UDP is a custom application-layer protocol designed for
decentralized group communication and distributed file sharing.

It operates over UDP and provides application-layer mechanisms
for reliability, message ordering, duplicate detection,
peer discovery, and file transfer.

Every participating peer can act as both a message sender
and a receiver.

The protocol does not require a permanent central server.

## 2. Protocol Design Objectives

- Support communication between at least four peers.
- Discover peers without a permanent central server.
- Maintain updated peer membership information.
- Support reliable group chat.
- Provide reliable data transfer over UDP.
- Support distributed storage of file chunks.
- Maintain at least two replicas of every chunk.
- Support parallel multi-source downloads.
- Recover from peer failures during file transfers.

## 3. General Packet Format

Every application-layer packet consists of:

1. Fixed-size protocol header.
2. Variable-length payload.

### 3.1 Header Structure

The protocol uses a fixed-size 56-byte header.

| Field | Size | Description |
|---|---:|---|
| Magic | 4 bytes | Protocol identifier: P2P1 |
| Version | 1 byte | Protocol version |
| Message Type | 1 byte | Identifies packet operation |
| Flags | 2 bytes | Control flags |
| Sender ID | 16 bytes | UUID of sending peer |
| Receiver ID | 16 bytes | UUID of destination peer |
| Message ID | 8 bytes | Unique message identifier |
| Sequence Number | 4 bytes | Sequence number |
| Payload Length | 4 bytes | Payload size in bytes |
| Total | 56 bytes | Fixed header size |

### 3.2 Field Definitions

**Magic:** Identifies packets belonging to this protocol.

**Version:** Identifies the protocol version. Initial value is 1.

**Message Type:** Specifies the operation represented by the packet.

**Flags:** Reserved for control information and future extensions.

**Sender ID:** Unique 128-bit UUID assigned to each peer.

**Receiver ID:** Destination peer UUID. An all-zero UUID indicates
a broadcast message.

**Message ID:** Unique 64-bit identifier used for message
identification and duplicate detection.

**Sequence Number:** 32-bit sequence number used for ordering
and reliable communication.

**Payload Length:** Specifies the number of bytes in the payload.

### 3.3 Encoding Rules

- All multibyte integer fields use big-endian encoding.
- UUIDs are transmitted as 16 raw bytes.
- Strings use UTF-8 encoding.
- Variable-length fields use explicit length prefixes.
- Payload length must match the actual payload size.
- Packets with invalid magic, unsupported versions,
  or invalid lengths are rejected.

## 4. Message Type Registry

The following message type identifiers are reserved.

| ID | Message Type | Purpose |
|---:|---|---|
| 1 | DISCOVER | Discover active peers |
| 2 | JOIN | Announce a new peer |
| 3 | JOIN_ACK | Acknowledge a joining peer |
| 4 | LEAVE | Announce peer departure |
| 5 | HEARTBEAT | Indicate that a peer is active |
| 6 | PEER_LIST | Exchange membership information |
| 7 | CHAT | Send group chat messages |
| 8 | ACK | Acknowledge received messages |
| 9 | NACK | Indicate rejection or missing data |
| 10 | CHUNK_REQUEST | Request a file chunk |
| 11 | CHUNK_DATA | Transfer chunk segments |
| 12 | FILE_METADATA | Share file information |
| 13 | CHUNK_LOCATION | Exchange chunk locations |
| 14 | FILE_LIST_REQUEST | Request shared-file catalog |
| 15 | FILE_LIST_RESPONSE | Return shared-file catalog |
| 16 | WINDOW_UPDATE | Update transfer window |
| 17 | TRANSFER_COMPLETE | Indicate completed transfer |
| 18 | ERROR | Report protocol errors |

Message identifiers are reserved for protocol version 1.

## 5. Message Payload Definitions

### 5.1 DISCOVER

Purpose: Search for active peers on the local network.

Payload:
- Listening UDP port (16-bit unsigned integer).
- Protocol capabilities.

### 5.2 JOIN

Purpose: Announce that a peer wants to join the group.

Payload:
- Peer name (UTF-8).
- Listening UDP port (16-bit unsigned integer).

### 5.3 JOIN_ACK

Purpose: Respond to a joining peer.

Payload:
- Acceptance status.
- Responding peer information.

### 5.4 LEAVE

Purpose: Announce a peer's planned departure.

Payload:
- Departure reason.

### 5.5 HEARTBEAT

Purpose: Indicate that a peer is still active.

Payload:
- Heartbeat counter (32-bit unsigned integer).

### 5.6 PEER_LIST

Purpose: Exchange information about known peers.

Payload:
- Number of peers.
- Peer UUIDs.
- IP addresses.
- UDP ports.
- Peer status.

### 5.7 CHAT

Purpose: Distribute a group chat message.

Payload:
- Chat message text (UTF-8).
- Sender sequence number.

### 5.8 ACK

Purpose: Acknowledge successful receipt of a reliable message.

Payload:
- Acknowledged message ID (64-bit unsigned integer).
- Acknowledged sequence number (32-bit unsigned integer).

### 5.9 NACK

Purpose: Indicate that a message or requested operation
could not be accepted.

Payload:
- Referenced message ID.
- Error or rejection reason.

### 5.10 CHUNK_REQUEST

Purpose: Request a particular file chunk from another peer.

Payload:
- File ID.
- Chunk index.
- Transfer ID.

### 5.11 CHUNK_DATA

Purpose: Transfer a portion of a file chunk.

Payload:
- Transfer ID.
- Chunk index.
- Segment offset.
- Segment data.

### 5.12 FILE_METADATA

Purpose: Exchange information about shared files.

Payload:
- File ID.
- Filename.
- File size.
- Chunk size.
- Total number of chunks.
- SHA-256 file hash.

### 5.13 CHUNK_LOCATION

Purpose: Inform peers where file chunks are stored.

Payload:
- File ID.
- Chunk index.
- Number of replicas.
- Replica peer UUIDs.

### 5.14 FILE_LIST_REQUEST

Purpose: Request the list of available shared files.

Payload:
- Request identifier.

### 5.15 FILE_LIST_RESPONSE

Purpose: Return the available shared-file catalog.

Payload:
- Number of shared files.
- File metadata.
- Chunk locations.

### 5.16 WINDOW_UPDATE

Purpose: Communicate available receive-window capacity
during reliable file transfers.

Payload:
- Transfer ID.
- Next expected sequence number.
- Available window size.

### 5.17 TRANSFER_COMPLETE

Purpose: Confirm completion of a file or chunk transfer.

Payload:
- Transfer ID.
- File ID.
- Completion status.

### 5.18 ERROR

Purpose: Report protocol or operation errors.

Payload:
- Error code.
- Error description.

## 6. Reliability Mechanisms

UDP does not guarantee delivery, ordering, or duplicate prevention.

P2P-UDP implements these mechanisms at the application layer.

### 6.1 Acknowledgements

Reliable messages require acknowledgements from their receivers.

The receiver sends an ACK after accepting a message.

### 6.2 Retransmissions

If an acknowledgement is not received before the
retransmission timeout, the sender retransmits the message.

Retransmissions retain the original message ID.

### 6.3 Duplicate Detection

Receivers maintain records of previously processed message IDs.

Duplicate messages are not delivered to the application again.

Previously processed reliable messages are acknowledged again
when retransmitted.

### 6.4 Message Ordering

Each sender maintains an independent sequence counter
for its chat stream.

Receivers buffer out-of-order messages until missing
sequence numbers arrive.

The system guarantees per-sender ordering rather than
a single global ordering across all peers.

### 6.5 Sliding Window

File transfers use a sliding-window mechanism.

Multiple segments can be transmitted without waiting
for an individual acknowledgement for every segment.

Window updates and acknowledgements control the sender's
outstanding data.

### 6.6 Stream Separation

Chat and file transfers maintain separate logical
sequence spaces and transfer states.

This prevents large file transfers from interfering
with chat message ordering.

## 7. Peer Discovery and Membership

### 7.1 Discovery

Peers use LAN UDP broadcast to discover other peers.

A newly started peer periodically broadcasts DISCOVER
messages until it discovers active group members.

### 7.2 Joining

1. New peer broadcasts DISCOVER.
2. Existing peers respond with JOIN_ACK and membership information.
3. New peer sends JOIN announcements.
4. Existing peers update their membership tables.
5. The joining peer requests shared-file metadata.
6. Peers exchange file and chunk location information.

### 7.3 Heartbeats

Every peer periodically sends HEARTBEAT messages.

Other peers update the last-seen timestamp of the sender.

### 7.4 Failure Detection

If a peer does not send a heartbeat within the configured
failure timeout, it is marked inactive.

The peer's known chunk replicas are checked for availability.

### 7.5 Leaving

A peer sends a LEAVE message before planned shutdown.

Other peers update their membership tables and
consider replacement replicas when necessary.

## 8. Group Chat Operation

1. Sender creates a CHAT message.
2. Sender assigns a unique message ID.
3. Sender increments its chat sequence number.
4. CHAT is sent to all known active peers.
5. Receivers check for duplicates.
6. Receivers acknowledge accepted messages.
7. Messages are buffered if received out of order.
8. Messages are delivered in sender sequence order.
9. Missing messages are recovered through retransmission.

## 9. Distributed File Storage

### 9.1 File Chunking

Every shared file is divided into fixed-size chunks.

Initial chunk size: 256 KiB.

Each chunk is assigned:
- File ID.
- Chunk index.
- Chunk size.
- SHA-256 chunk hash.

### 9.2 Chunk Distribution

Chunks are distributed across multiple peers.

A complete file must not be held by one peer as the
distributed shared-file representation.

### 9.3 Replication

Every chunk must have at least two replicas on
different peers.

A chunk is advertised as replicated only after
storage acknowledgements are received from two peers.

### 9.4 File Metadata

Peers maintain metadata describing:
- Available files.
- File sizes.
- Chunk counts.
- Chunk hashes.
- Replica locations.

## 10. Multi-Source File Download

1. Downloader requests the shared-file catalog.
2. Downloader selects a file.
3. Downloader obtains chunk location information.
4. Downloader identifies available replicas.
5. Different chunks are requested from different peers.
6. Multiple chunk transfers execute concurrently.
7. Received segments are reassembled into chunks.
8. Chunk hashes are verified.
9. The complete file is reconstructed.
10. Final SHA-256 integrity verification is performed.

## 11. Fault Tolerance

If a peer fails during a download:

1. The downloader detects a timeout or failed transfer.
2. The current source is marked unavailable for that request.
3. The downloader checks alternative replica locations.
4. The missing chunk or segment is requested from another peer.
5. The download continues.
6. The completed file is verified.

If a replica is permanently lost, available peers
may create replacement replicas when sufficient data
and storage capacity are available.

## 12. Initial Protocol Parameters

| Parameter | Initial Value |
|---|---:|
| Protocol version | 1 |
| Header size | 56 bytes |
| Heartbeat interval | 2 seconds |
| Peer failure timeout | 8 seconds |
| Initial retransmission timeout | 500 ms |
| Maximum retransmissions | 5 |
| File chunk size | 256 KiB |
| Maximum UDP datagram target | 1200 bytes |
| Minimum replicas per chunk | 2 |

These values are initial design parameters and
will be evaluated through experiments.

## 13. Design Constraints

- At least four simultaneous peers.
- At least two shared files per participant.
- Each shared file must be at least 2 MB.
- Every chunk must have at least two replicas.
- No permanent central server or central storage.
- Downloads must support multiple sources.
- A download must survive the loss of one source
  if another replica is available.

## 14. Future Extensions

Possible extensions include:

- Re-replication after peer failure.
- Private one-to-one messaging.
- Encryption of messages and file transfers.
- Persistent chat history.
- Improved peer discovery.
- Dynamic storage allocation.
- Adaptive retransmission timeout.

## 15. Implementation Status

Current status: Initial protocol design.

The specification will be refined before implementation
to define exact binary payload serialization, message
validation, acknowledgement behavior, and operation
state transitions.

All peers implementing this protocol version must
follow the same packet and payload definitions.
