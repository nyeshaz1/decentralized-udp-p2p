# ROLE: AREESHA. Branch: feat/areesha-membership-chat
Folders: src/p2p/membership/, src/p2p/chat/, tests/test_membership.py, tests/test_chat.py.

## Task A1: Payload codecs (Mon 23) in src/p2p/membership/messages.py and src/p2p/chat/messages.py
encode/decode functions for DISCOVER, DISCOVER_REPLY, JOIN, JOIN_ACK (status, members, manifests as opaque bytes blobs with u32 length prefix, chunk_map entries), MEMBER_UPDATE, LEAVE, HEARTBEAT, CHAT, PRIVATE_MSG exactly as protocol.md section 3 (str8 = u8 length + UTF-8; ip4 = 4 bytes; fid = 16 bytes). Test each against hand-written bytes and with round trips, including empty member list and a name of 255 bytes.

## Task A2: Membership (Mon 23 and Tue 24) in src/p2p/membership/membership.py
`class Membership(MembershipView)`, constructor `Membership(transport, my_id, my_port, name="", bootstrap=None)`. Interface (the leader's node.py calls exactly this):
- `start()` registers handlers for DISCOVER, DISCOVER_REPLY, JOIN, JOIN_ACK, MEMBER_UPDATE, LEAVE, HEARTBEAT and starts the heartbeat/failure thread. `stop()`.
- `join()`: protocol.md 6.1. With `bootstrap=(ip, port)` send JOIN there directly; otherwise broadcast DISCOVER (port DISCOVERY_PORT), retry every 2 s up to 3 times, then run alone (first peer). Upon the first JOIN_ACK: merge members, call `state_consumer(manifests, chunk_map)`, send JOIN to every other listed member. Handle JOIN_ACK status 1 (ID_IN_USE): raise/exit with a clear error.
- `leave()`: send LEAVE reliably to all alive peers, wait up to 1 s, stop.
- `alive_peers() -> {peer_id: (ip, port)}` (excludes self); `on_change(cb)` with `cb(event, peer_id)`, event in `"join" | "leave" | "fail"` (call callbacks from a separate thread or after releasing locks, never while holding the peer-table lock); `peer_name(id)`; `report_unreachable(addr)` marks the peer at that address failed.
- Public attributes `state_provider` and `state_consumer` (callables, default to empty lists/no-op). On JOIN: reply JOIN_ACK with `state_provider()` data and my members list (including me), then send MEMBER_UPDATE(JOINED) to all OTHER members.
- Heartbeat: every HEARTBEAT_INTERVAL send HEARTBEAT (unreliable) to every alive peer. Any valid packet from a peer refreshes last_seen (so also refresh in every handler, using sender_id). A peer silent for PEER_TIMEOUT is FAILED: remove it, fire `"fail"`, send MEMBER_UPDATE(FAILED) to all other alive peers. Ignore MEMBER_UPDATE(FAILED) for peers already failed (idempotent). MEMBER_UPDATE(JOINED) for an unknown peer adds it without a reply.
- LEAVE received: remove peer, fire `"leave"`.
- A JOIN from a failed/left peer id is a normal re-join. A JOIN with an id in use by an alive peer at a different address gets JOIN_ACK status 1.
- Never hold the peer-table lock while sending.
Tests with FakeNetwork (tests/test_membership.py): 4 peers join via bootstrap and all lists converge to 4 within 5 s; same via broadcast DISCOVER; `kill()` a peer and all others fire "fail" within PEER_TIMEOUT + 2 s (use a shortened timeout via config monkeypatch or a constructor override); graceful leave fires "leave" immediately; duplicate id rejected; state_provider data reaches the joiner's state_consumer; HEARTBEAT loss of 30 % does not cause false failures (heartbeats every 1 s, 5 s timeout).

## Task A3: Chat (Wed 25) in src/p2p/chat/chat.py
`Chat(transport, membership, my_id, on_message)`. `send(text)`: next `chat_seq` (starts 1), CHAT reliably to every peer in `alive_peers()` (text max 1000 bytes UTF-8, reject longer with ValueError). Receiver: `expected[sender]` initialised to the first chat_seq seen from that sender; lower = drop; equal = deliver then flush consecutive buffered; higher = buffer (cap the buffer at 1000 and log if exceeded). Reset a sender's state when membership fires "leave" or "fail" for it. `send_private(peer_id, text)` sends PRIVATE_MSG (stretch, Fri 27). `on_message(sender_id, text, private)` is called outside locks. Tests: in-order delivery, duplicate dropped, out-of-order (feed handler directly with seq 3, 1, 2 and expect 1, 2, 3), two senders independent, a late joiner receives only new messages, messages sent to 3 peers all arrive, private message reaches only the target.

## Task A4: Report and 2-3 laptop test (Sat 28)
Write the report sections for discovery, membership, failure detection and chat ordering (design, alternatives, reasoning, a flow diagram for join and crash). Test the real network on 2-3 laptops using a phone hotspot: broadcast discovery, bootstrap fallback, firewall (allow Python for UDP on private networks), and note findings for the leader.

## Definition of done (Areesha)
All tests green; 4 fake peers converge; failure detected in under 7 s; chat order guaranteed under reordering/duplicates; PR #1 Mon, PR #2 Tue; no edits outside your folders.