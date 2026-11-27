# Progress Log: Ayesha (Leader)
Branch: feat/leader-transport | Owns: common/, transport/, node.py, cli.py, experiments, report, PR reviews
Deadline: Tue 1 Dec 23:59 | Team target: Sun 29 Nov | 30 Nov and 1 Dec = buffer

## 1. Overall status (end of Tue 24 Nov)
| Part | Owner | Status |
|---|---|---|
| Repo, branches, docs (architecture, design decisions, roadmap, protocol v1.1) | Ayesha | done |
| Codec with `session` byte, fake in-memory transport, team briefs | Ayesha | done |
| Transport (Task L1) | Ayesha | done, 14 tests |
| node.py and CLI (Task L2) | Ayesha | Wed 25 |
| Membership and chat | Areesha | not delivered yet (asked 5 questions, answered) |
| Storage and transfer | Hamza | not delivered yet |
| Experiments, report, demo | Ayesha | Fri 27 to Sun 29 |

Approx. progress: about 35% of leader work, about 25% of the whole project.

## 2. Setup (done)
- Repo skeleton, docs, protocol v1.1 with payload layouts, codec `session` byte
- Fake in-memory transport (`tests/fake_transport.py`), `Transport.set_unreachable_handler`
- Team briefs in `docs/team_briefs/` (common, leader, areesha, hamza), synced to all branches
- Branches: main, develop, feat/leader-transport, feat/areesha-membership-chat, feat/hamza-storage-transfer
- Instruction message sent to Areesha and Hamza

## 3. Transport (Task L1) completed
| Task | Status |
|---|---|
| Sockets, unreliable send/receive, broadcast, loss simulation, stats | done |
| `send_reliable`: fragmentation (1024 B), seq numbers, window 32 | done |
| Receive side: ACK, in-order delivery, dedup, reassembly | done |
| T1 20% loss, 1 MB intact (about 30 s) | done |
| T2 RFC 6298 adaptive RTO, Karn rule, fast retransmit after 3 SACKed packets | done |
| T3 Unreachable callback after 8 retries (counter resets on any ACK/SACK) | done |
| T4 Duplicate packet delivered once (test) | done |
| T5 Session reset (test) | done |
| T6 SACK in ACK (test) | done |
| T7 Review and merge PRs | blocked: no PRs yet |

### Problems found and fixed (good viva material)
| Problem | Cause | Fix |
|---|---|---|
| srtt was seconds on localhost | RTT sampled from hole-filling cumulative ACKs | sample only clean ACKs (Karn), one per ACK |
| RTO stuck at 3 s | backoff applied per packet | back off only when the oldest packet times out |
| Window stalled under loss | wait for timer on lost oldest packet | fast retransmit after 3 SACKed packets |
| Live peer declared dead under 20% loss | retry counter never reset | reset retries on any ACK/SACK |
| 20% test flaky | MAX_RETRIES=8 too low for 36% effective loss | test uses MAX_RETRIES=30 (default stays 8) |
| Receiver thread died when a peer was killed (Windows) | ConnectionResetError treated as fatal | ignore ConnectionResetError |
Result: 1 MB at 20% loss went from 100+ s (and failing) to about 30 s.

### Viva summary
1. Selective Repeat with window 32, only lost packets resent.
2. Cumulative ACK plus SACK bitmap.
3. Receiver buffers out-of-order, delivers in order, drops duplicates.
4. Fragmentation into 1024 B packets, reassembled by MORE_FRAG flag.
5. Session byte detects a restarted peer and resets state.
6. Adaptive RTO (RFC 6298) with Karn's rule; fast retransmit; unreachable callback feeds failure detection.

## 4. Open items from Tuesday
1. Verify the flaky-test fix (`monkeypatch MAX_RETRIES=30`): run `python -m pytest -q` twice, expect 14 passed both times.
2. Push to develop, then `git checkout feat/leader-transport` and `git merge develop`.
3. Commit and push this progress log.
4. Add Areesha and Hamza as GitHub collaborators (need usernames), then enable branch protection on main and develop.

## 5. Answers sent to Areesha (decisions)
- JOIN_ACK replier entry uses ip `0.0.0.0`; the joiner substitutes the packet source IP.
- state_provider returns (manifests, chunk_map); state_consumer takes the same.
- HEARTBEATs from peers not in the alive table are ignored.
- First DISCOVER_REPLY wins; no answer after 3 tries means run alone. With `--bootstrap`, a dead bootstrap raises `MembershipError`.
- Optional kwargs `heartbeat_interval`, `peer_timeout`; ValueError for name over 255 bytes; `MembershipError` for ID_IN_USE (defined in membership/membership.py).

## 6. Plan for Wednesday 25 Nov (Task L2: Node and CLI)
| # | Task | Done when |
|---|---|---|
| W1 | Ask Areesha and Hamza for PR status and a firm ETA | ETAs known |
| W2 | Review and merge PRs (order: membership, storage, chat, transfer) | tests pass on develop after each merge |
| W3 | `git merge develop` into feat/leader-transport after each merge | branch up to date |
| W4 | Write `src/p2p/node.py`: build ReliableUDP, Membership, Chat, StorageManager, TransferService; wire state_provider, state_consumer, set_unreachable_handler; start/stop/leave; catch MembershipError | Node starts and stops cleanly |
| W5 | Write `src/p2p/cli.py`: args --id --port --bootstrap --name --share --loss; commands /peers /files /share /download /msg /chunks /stats /quit; plain text = chat | CLI runs |
| W6 | `scripts/run_local.ps1`: 4 peers on ports 5001 to 5004 (bootstrap 127.0.0.1:5001) | 4 peers see each other |
| W7 | First 3-peer run on one laptop | chat works, peer list correct |
| W8 | Update this log and push | log current |

### Things to consider
- If their PRs are late, build node.py and cli.py against stand-in classes.
- Set `$env:PYTHONPATH="src"` in every new terminal.
- Separate data dir per peer (`node_data/<id>`).
- Allow Python through Windows Firewall (UDP, private networks).
- Do not change protocol.md or common/ without telling the team.
- For Friday's loss experiments set `config.MAX_RETRIES = 30` in the script.

## 7. Remaining schedule
| Day | Leader task |
|---|---|
| Thu 26 | integration fixes, 4-peer run, kill a peer mid-download works |
| Fri 27 | experiments (loss 0/5/10/20 %, chunk size, failover time), feature freeze at night |
| Sat 28 | graphs, report, flow diagrams, release candidate |
| Sun 29 | develop -> main, demo rehearsal, submission zip |
| Mon 30 to Tue 1 | buffer, fixes only, submit on LMS |

## 8. Risks
| Risk | Mitigation |
|---|---|
| Members' PRs late | ask for status Wed morning; drop stretch features first |
| Transport bugs under loss | test at 0, 5, 10, 20%; log retransmit counters |
| Broadcast blocked on Wi-Fi | phone hotspot plus `--bootstrap` fallback |
| Windows Firewall blocks UDP | allow Python on private networks |

## 9. Daily log
- Sun 22: setup complete, transport steps 0 to 4 done, 9 tests passing.
- Mon 23: transport reliable path (ACK/SACK, reassembly, fixed RTO), tests added.
- Tue 24: T1 to T6 done, 14 tests; fixes listed in section 3; answered Areesha's 5 questions; PRs from Areesha and Hamza not yet received.





## Status at end of Fri 27 Nov
- node.py, cli.py and tests/test_node.py done, merged into develop (aa7e81f).
- Areesha's membership + chat PR merged; 65 tests passed on develop.
- scripts/run_local.ps1 done. First multi-peer run on one laptop: peer list correct, group chat works, private message works, crash detection works (closed a window, peer removed from /peers within seconds).
- Cosmetic: the "> " prompt is not redrawn after an incoming message (harmless, skipped).
- Waiting on Hamza's PR (storage + transfer). File commands (/share /files /download /chunks) are wired in node.py and activate automatically once his modules are merged.

## Next
1. Review Hamza's PR: run his tests, check he touched only storage/ and transfer/, merge to develop, sync my branch.
2. Run 4 peers, share a file, download it, kill a source mid-download.
3. Experiments (loss 0/5/10/20 %, chunk size, failover time), set config.MAX_RETRIES = 30 in the script.
4. Report, diagrams, graphs (Sat), develop -> main, zip, rehearsal (Sun).