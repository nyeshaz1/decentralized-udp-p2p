# Architecture

Layers (top to bottom):
1. CLI (cli.py): chat, /files, /download, /peers
2. Services: chat/, membership/, storage/, transfer/
3. Reliable transport: transport/reliable_udp.py (sequence, ACK/SACK, RTO, fragmentation)
4. Codec: common/protocol.py (24-byte header pack/unpack)
5. UDP socket

node.py wires all services to one Transport and dispatches incoming messages by type.

Threads: one receiver thread, one timer thread (retransmit, heartbeat), a worker pool for chunk downloads.
Services never touch sockets; they only use the Transport interface in common/interfaces.py.

Data: peer table (membership), manifest store, chunk store on disk (node_data/<id>/chunks/), chunk location map (file_id, idx) -> [peer ids].
