# Roadmap
- Phase 0: skeleton, protocol freeze, branches (leader)
- Phase 1: codec + fake transport + unit tests (all)
- Phase 2: real reliable UDP transport (leader); membership + chat (Areesha); chunking + placement + store (Hamza)
- Phase 3: integration in node.py, join flow, file manifest sync
- Phase 4: multi-source download + failover + re-replication
- Phase 5: experiments (loss 0/5/10/20 %, throughput, recovery time), graphs
- Phase 6: report, flow diagrams, demo rehearsal (kill a peer mid-download)
Merge rule: each phase ends with a PR into develop, leader reviews and merges.
