# Design Decisions

| # | Area | Chosen | Alternatives | Trade-off / reason |
|---|---|---|---|---|
| 1 | Topology | Full mesh | Tree, ring, DHT | Group is small (4-10 peers), simplest and no routing needed |
| 2 | Reliability | Selective Repeat + cumulative ACK + SACK | Stop-and-wait, Go-Back-N | Fewer retransmissions under loss, buffers cost memory |
| 3 | Timers | RFC 6298 SRTT/RTTVAR, RTO 0.2-3 s | Fixed timeout | Adapts to LAN vs hotspot latency |
| 4 | Window | Fixed 32, no congestion control | AIMD | Congestion control explicitly optional in the brief |
| 5 | Fragmentation | 1024 B payload per datagram, MORE_FRAG flag | 1400 B | Stays under typical MTU, no IP fragmentation |
| 6 | Chunk size | 64 KiB (to be measured: 16/64/256) | | Small = more overhead, large = costly retry |
| 7 | Replication | R = 2 | R = 3 | Meets "at least two"; R=3 costs 50 % more storage and bandwidth |
| 8 | Placement | HRW (rendezvous) hashing | Round-robin, ring | Deterministic on every peer, minimal movement on churn |
| 9 | Failure detection | Heartbeat 1 s, timeout 5 s | SWIM, phi-accrual | Simple and testable; slower detection is acceptable |
| 10 | Membership dissemination | Gossip MEMBER_UPDATE (reliable) | Central tracker | Brief forbids central server |
| 11 | Discovery | LAN broadcast + bootstrap fallback | Multicast only | Broadcast may be blocked, so bootstrap is the safety net |
| 12 | Chat ordering | Per-sender chat_seq + dedup | Total order, vector clocks | Brief requires only per-sender order |
| 13 | Integrity | SHA-256 per chunk and per file, CRC32 per packet | CRC only | Detects corruption and wrong chunks |
| 14 | Download scheduling | Parallel workers, alternate replicas, retry on other replica | Sequential, rarest-first | Meets multi-source requirement, simple failover |
| 15 | Language | Python stdlib | C/Java | Fast to build, performance enough for demo |
| 16 | Peer restart handling | 1-byte session id in header; new session resets transport state | Persistent state, timestamps | Lets a crashed peer rejoin with the same id and port and restart seq at 1 |
| 17 | Fragmentation delivery | Each fragment is its own reliable packet; reassembly relies on in-order delivery | Separate fragment IDs and offsets | Simpler, no extra reassembly state beyond a buffer |

Measured results (chunk size, loss vs throughput, failover time) are added here after Fri 27 Nov.