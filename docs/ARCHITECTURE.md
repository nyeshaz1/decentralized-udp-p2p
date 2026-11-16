
# System Architecture

## 1. Overview

The application follows a decentralized peer-to-peer architecture.

Every running application instance represents one peer.
All peers execute the same software and can initiate
communication or respond to requests.

No permanent central server is required.

## 2. Peer Components

Each peer consists of the following logical components:

### 2.1 Networking Layer
Responsible for:
- Creating UDP sockets.
- Sending and receiving datagrams.
- Encoding and decoding protocol packets.
- Routing received messages to appropriate handlers.

### 2.2 Discovery and Membership Layer
Responsible for:
- Discovering other peers.
- Maintaining peer information.
- Processing JOIN and LEAVE messages.
- Sending and receiving heartbeats.
- Detecting inactive peers.

### 2.3 Reliability Layer
Responsible for:
- Sequence numbering.
- Acknowledgements.
- Retransmissions.
- Duplicate detection.
- Ordered delivery.
- Reliable data transfer.

### 2.4 Chat Layer
Responsible for:
- Sending group messages.
- Receiving group messages.
- Maintaining message history.
- Delivering messages in per-sender order.

### 2.5 Distributed Storage Layer
Responsible for:
- Dividing files into chunks.
- Maintaining file metadata.
- Tracking chunk locations.
- Storing chunk replicas.
- Managing local storage responsibilities.

### 2.6 File Transfer Layer
Responsible for:
- Handling chunk requests.
- Sending chunk data.
- Downloading from multiple peers.
- Reassembling files.
- Verifying file integrity.
- Switching to replicas after failures.

## 3. Peer Information

Each peer maintains a local peer table containing:

- Peer ID
- IP address
- UDP port
- Last heartbeat time
- Peer status

Each peer independently maintains its own view
of group membership.

## 4. File Metadata

A shared file is represented by:

- File ID
- File name
- File size
- Chunk size
- Number of chunks
- SHA-256 hash
- Chunk locations

Each chunk has:
- Chunk index
- Chunk hash
- Replica peer IDs

## 5. Communication Model

All peer-to-peer communication takes place using UDP.

Application-layer reliability mechanisms provide
acknowledgements, retransmissions, sequencing,
and duplicate suppression where required.

## 6. Fault Tolerance

If a peer becomes unavailable:
- Its membership entry is marked inactive.
- Other peers identify affected chunk replicas.
- Downloading peers select alternative replicas.
- Available peers can restore missing replicas.

## 7. Design Principle

No peer is permanently responsible for coordinating
the entire system.

Every peer maintains its own local state and
participates in communication, storage, and transfer.
