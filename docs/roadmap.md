# Roadmap (deadline: Tue 1 Dec 23:59; team target: Sun 29 Nov; 30 Nov-1 Dec = buffer)

| Date | Leader | Areesha | Hamza | Gate |
|---|---|---|---|---|
| Sun 22 | Skeleton, protocol freeze, branches, briefs sent | Clone, read docs, set up venv | Same | Everyone can run `pytest` |
| Mon 23 | Transport v1: sequence, ACK, retransmit | Membership: peer table, heartbeat, failure detector (fake transport) | Chunker, SHA-256 manifest, HRW placement (unit tests) | PR #1 by night |
| Tue 24 | Transport v2: SACK, RTO, fragmentation, loss simulator | Discovery (broadcast + bootstrap), JOIN/JOIN_ACK | Chunk store on disk, CHUNK_STORE/REQUEST/DATA handlers | PR #2: all modules merged into develop |
| Wed 25 | node.py + CLI, wiring all services | Chat: chat_seq, dedup, in-order delivery | Multi-source download (parallel workers) | First 3-peer run on one laptop |
| Thu 26 | Integration fixes, 4-peer run | Join-time sync of members, manifests and chunk map | Failover to another replica, retries | Kill a peer mid-download and it still completes |
| Fri 27 | Experiments script (loss 0/5/10/20 %) | Stretch: private messages | Stretch: re-replication | Feature freeze at night |
| Sat 28 | Graphs, report, flow diagrams | Test on 2-3 laptops (hotspot), report sections | Report sections, chunk-size experiment | Release candidate on develop |
| Sun 29 | develop -> main, demo rehearsal, zip | Rehearse | Rehearse | Submission zip ready |
| Mon 30-Tue 1 | Buffer, fixes only, submit on LMS | | | |

Merge rule: PR into develop, leader reviews, tests must pass.
Rule: if a task slips a day, drop stretch features first, never core ones.