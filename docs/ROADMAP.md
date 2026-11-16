
# Project Development Roadmap

## Phase 0: Project Foundation
- Create GitHub repository.
- Establish project directory structure.
- Define system architecture.
- Define application-layer protocol.
- Document initial design decisions.

## Phase 1: UDP Networking Foundation
- Create UDP socket communication.
- Implement peer identification.
- Implement packet encoding and decoding.
- Test communication between multiple processes.

## Phase 2: Peer Discovery and Membership
- Implement LAN broadcast discovery.
- Implement JOIN and LEAVE operations.
- Implement periodic HEARTBEAT messages.
- Detect inactive and crashed peers.
- Maintain peer membership tables.

## Phase 3: Reliable UDP Communication
- Implement message identifiers.
- Implement sequence numbering.
- Implement acknowledgements.
- Implement retransmission after timeout.
- Prevent duplicate delivery.
- Implement ordered message delivery.
- Implement sliding-window data transfer.

## Phase 4: Group Chat
- Implement group message broadcasting.
- Guarantee per-sender message ordering.
- Prevent duplicate message delivery.
- Maintain message history.

## Phase 5: Distributed File Storage
- Support at least two shared files per participant.
- Split files into fixed-size chunks.
- Generate file and chunk metadata.
- Distribute chunks across different peers.
- Maintain at least two replicas per chunk.

## Phase 6: Peer Joining and Storage Management
- Exchange shared-file catalogs.
- Exchange chunk location metadata.
- Assign storage responsibilities to joining peers.
- Update replica locations.

## Phase 7: Multi-Source File Downloads
- Request chunks from multiple peers.
- Download chunks concurrently.
- Reassemble downloaded files.
- Verify integrity using SHA-256.

## Phase 8: Fault Tolerance
- Detect failed peers.
- Retry failed chunk requests.
- Switch to available replicas.
- Complete downloads despite peer failure.
- Re-replicate lost chunks when possible.

## Phase 9: Testing and Performance Evaluation
- Test with at least four peers.
- Measure chat delivery reliability.
- Measure file transfer throughput.
- Test packet loss and delay.
- Test peer crashes during downloads.
- Generate performance graphs.

## Phase 10: Final Submission
- Complete technical report.
- Document protocol and architecture.
- Include operation flow diagrams.
- Include measured results and graphs.
- Prepare installation instructions.
- Package source code and documentation.
- Perform live demonstration.
