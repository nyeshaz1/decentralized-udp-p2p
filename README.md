
# Decentralized UDP-Based P2P Communication System

## Project Overview

This project implements a decentralized, multi-party communication
application using UDP sockets.

Unlike traditional client-server applications, the system does not
depend on a permanent central server or central storage.

Every participant acts as both a client and a server, allowing peers
to communicate, exchange files, and share storage responsibilities.

## Objectives

- Support at least four simultaneous peers.
- Discover peers without a permanent central server.
- Maintain active peer membership.
- Provide reliable group chat over UDP.
- Implement application-layer reliability.
- Divide shared files into fixed-size chunks.
- Distribute chunks across different peers.
- Maintain at least two replicas of every chunk.
- Support parallel multi-source downloads.
- Recover from peer failures during downloads.
- Verify file integrity using SHA-256.

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python 3 |
| Transport Protocol | UDP |
| Concurrency | Python threading |
| Version Control | Git and GitHub |
| File Integrity | SHA-256 |
| Testing | Multi-process peer simulation |

## Architecture

The system follows a decentralized peer-to-peer architecture.

Each peer independently maintains:
- A peer membership table.
- A chat message history.
- A local chunk storage directory.
- File and chunk metadata.
- Active communication and transfer state.

There is no permanent central coordinator.

## Project Structure

See the project directory structure and documentation
in the `docs/` directory.

## Documentation

- [Project Roadmap](docs/ROADMAP.md)
- [Protocol Specification](docs/PROTOCOL.md)
- [System Architecture](docs/ARCHITECTURE.md)
- [Design Decisions](docs/DESIGN_DECISIONS.md)

## Development Status

Current phase: Project Foundation and Protocol Design.

Implementation has not started yet.

## Team

Three-member academic project.

## Course

Computer Networks

## License

Academic project.
