
# Initial Design Decisions

This document records the initial architectural choices
and the reasons behind them.

These decisions may be revised after testing and analysis.

| Area | Initial Decision | Reason |
|---|---|---|
| Transport | UDP | Required by project |
| Programming language | Python 3 | Socket and concurrency support |
| Architecture | Decentralized P2P | No permanent central server |
| Discovery | LAN broadcast | No permanent bootstrap dependency |
| Membership | Heartbeats and timeout | Detect failed peers |
| Peer identity | UUID | Unique peer identification |
| Packet format | Custom binary header | Consistent protocol |
| Byte order | Network byte order (big-endian) | Standardized packet encoding |
| Chat ordering | Per-sender sequence numbers | Preserve sender ordering |
| Duplicate prevention | Message ID tracking | Avoid duplicate delivery |
| Reliability | ACK and retransmission | Recover lost packets |
| Transfer reliability | Sliding window | Improve throughput |
| File chunking | Fixed-size chunks | Simplify storage and transfer |
| Replication | Minimum two copies | Fault tolerance |
| File integrity | SHA-256 | Detect corruption |
| Concurrency | Threads | Handle multiple activities |

## Constraints

- At least four simultaneous peers.
- At least two shared files per participant.
- Every shared file must be at least 2 MB.
- No complete file should be stored on a single peer
  as the distributed shared-file representation.
- Each chunk must have at least two replicas.
- Downloads must support at least two sources.
- A download must survive the loss of one source
  when another replica is available.

## Open Design Questions

1. How will peers resolve conflicting membership information?
2. How will chunk ownership be assigned?
3. How will replicas be redistributed when a peer joins?
4. How will simultaneous file transfers be scheduled?
5. What timeout and retransmission values will be used?
6. How will peers recover if metadata becomes inconsistent?
7. How will the system handle temporary network partitions?

These questions will be resolved during protocol design
and implementation.
