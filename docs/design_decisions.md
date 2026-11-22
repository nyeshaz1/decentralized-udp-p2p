# Design Decisions (alternatives considered)

| Area | Chosen | Alternatives | Why |
|---|---|---|---|
| Reliability | Selective Repeat + SACK | Stop-and-wait, Go-Back-N | Higher throughput under loss, fewer retransmits |
| Membership | Heartbeat + gossip | Central tracker, SWIM | Simple, testable, no server |
| Replica placement | HRW (rendezvous) hashing, R=2 | Round-robin, consistent-hash ring | Minimal chunk movement on churn, deterministic on every peer |
| Chunk size | 64 KiB | 16 KiB, 256 KiB | Balance of overhead and retry cost (to be measured) |
| Chat ordering | Per-sender chat_seq | Total order / vector clocks | Spec only requires per-sender order |
| Integrity | SHA-256 per chunk | CRC only | Detects corrupt or malicious chunks |
| Language | Python | C / Java | Fast development, good for demo |

(Update with measured results later.)
