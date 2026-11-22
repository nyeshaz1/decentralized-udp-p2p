# Progress Log: Ayesha (Leader)
Branch: feat/leader-transport | Owns: common/, transport/, node.py, cli.py, experiments, report, PR reviews

## Status at end of Sun 22 Nov

### Setup (done)
- Repo skeleton, docs (architecture, design_decisions, roadmap, protocol v1.1), codec with `session` byte
- Fake in-memory transport (`tests/fake_transport.py`), `Transport.set_unreachable_handler`
- Team briefs in `docs/team_briefs/` (common, leader, areesha, hamza), synced to all branches
- Branches pushed: main, develop, feat/leader-transport, feat/areesha-membership-chat, feat/hamza-storage-transfer
- Message with instructions sent to Areesha and Hamza

### Transport L1, Monday part (done, pushed, 9 tests passed)
| # | Step | Status |
|---|---|---|
| 0 | Sockets, unreliable send/receive, broadcast, loss simulation, stats | done |
| 1 | `send_reliable`: fragmentation (1024 B), seq numbers, window 32 | done |
| 2 | Receive side: ACK, in-order delivery, dedup, reassembly | done |
| 3 | Retransmit timer (fixed RTO 1 s) | done |
| 4 | Tests: 10 messages in order, 200 KB intact | done |
| 5 | Review PR #1 (Areesha, Hamza) | skipped Sun, do Mon evening |

Also already in code (planned for Tuesday): SACK send/read, session-change reset.

## Known gaps in the transport
1. Retransmission never tested under loss (tests ran on clean localhost).
2. Unreachable callback not implemented (retries counted, nothing happens after 8).
3. RTO is fixed 1 s, not RFC 6298 adaptive.
4. Retransmit of one packet does not drop the peer state yet.

## Plan for Tuesday 24 Nov
| # | Task | Done when |
|---|---|---|
| T1 | Loss test: loss_rate=0.2 on both sides, 1 MB arrives intact | test passes 3 runs in a row |
| T2 | RFC 6298 RTO: SRTT/RTTVAR, Karn rule, clamp 0.2 to 3 s, double on timeout | RTO values logged and sane |
| T3 | Unreachable callback after 8 retries, then drop peer state | test: stop one side, other calls callback |
| T4 | Duplicate injection test (same packet twice, delivered once) | test passes |
| T5 | Session reset test (restart peer, same port, seq restarts at 1) | test passes |
| T6 | SACK encode/decode round trip test | test passes |
| T7 | Review and merge PRs from Areesha and Hamza into develop | merged in order: transport, membership, storage |

## Things to consider tomorrow
- Start with T1. If 20% loss fails, fix before anything else; everything depends on it.
- Use shorter timeouts in tests (config override) so the unreachable test does not take 30 s.
- Use different ports per test (47xxx range) to avoid "address in use" between tests.
- Test with `$env:PYTHONPATH="src"` set in every new terminal.
- Merge order for PRs: common fixes, transport, membership, storage, chat, transfer, node/cli.
- Check each PR: payload offsets match protocol.md, no sockets in services, tests present and passing, only own folders edited.
- Pull develop into your branch after each merge: `git merge develop`.
- Wed 25 is node.py + CLI: needs Areesha's Membership and Hamza's Storage/Transfer merged by Tue night. Chase them Tue evening if not.
- Still to do: add Areesha and Hamza as collaborators (need usernames), then enable branch protection on main and develop.

## Risks
| Risk | Mitigation |
|---|---|
| Transport bugs under loss | Test at 0, 5, 10, 20% early; log retransmit counters |
| Members' PRs late | Ask for status Tue morning; drop stretch features first |
| Broadcast blocked on Wi-Fi | Phone hotspot plus `--bootstrap` fallback |
| Windows Firewall blocks UDP | Allow Python on private networks |

## Daily log
- Sun 22: setup complete, transport L1 steps 0 to 4 done, 9 tests passing.