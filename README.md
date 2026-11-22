# Decentralized UDP P2P Chat and File Sharing (CN Project)

Serverless, UDP-based group chat and distributed file storage with multi-source download.
Team: Leader (nyeshaz1), Areesha, Hamza.

## Run (filled in as modules land)
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python scripts/gen_testfiles.py          # creates 2 files >= 2 MB in shared_files/
    python -m p2p.cli --id 1 --port 5001     # first peer
    python -m p2p.cli --id 2 --port 5002 --bootstrap 127.0.0.1:5001

## Tests
    PYTHONPATH=src pytest -q

See docs/ for protocol, architecture, design decisions and roadmap.
