```markdown
# Appendix K – Rust Crate Reference & Workspace Structure

## K.1. General Principle
The source code of all system utilities and daemons is written in Rust and organized as a virtual
workspace. The list of dependencies, their exact versions, and the directory structure are no longer a
static table in the document. Instead, they are stored in a machine‑readable format as a
signed artifact in IPFS and are automatically generated from the `Cargo.toml` and `Cargo.lock` files.

This appendix contains:
- a reference to the current workspace artifact (CID),
- a description of the workspace structure and key crates,
- a table of key dependencies with versions (from `Cargo.lock`),
- the Minimum Supported Rust Version (MSRV),
- instructions for building, integrity checking, and reproducing the environment.

## K.2. Current Workspace Artifact

| Field              | Value                                                                          |
| :----------------- | :----------------------------------------------------------------------------- |
| **CID (IPFS)**     | `QmCoreToolsWorkspaceV2`                                                       |
| **BLAKE3 hash**    | `e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2`            |
| **Type**           | tar.gz archive with workspace source code                                     |
| **Version**        | 2.0.1 (corresponds to document version 0.3)                                   |
| **Signature**      | `ed25519:2b3c4d5e…`                                                           |

**Download and unpack:**
```bash
ipfs get QmCoreToolsWorkspaceV2 -o core-tools.tar.gz
tar -xzf core-tools.tar.gz
cd core-tools
```

## K.3. Workspace Structure
The virtual workspace `core-tools` combines several crates, each implementing a separate
system component. Directory structure:

```
core-tools/
├── Cargo.toml                 # Virtual workspace
├── Cargo.lock                 # Pinned dependency versions
├── rust-toolchain.toml        # Rust version (MSRV)
├── README.md                  # Build instructions
├── common/                    # Shared utilities and data structures
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs
│       ├── crypto.rs          # Signatures, hashes, Kyber, Dilithium
│       ├── ipfs.rs            # IPFS client
│       └── artifact.rs        # Artifact model (section 2.12)
├── watchdogd/                 # Hardware watchdog daemon (section 4.9)
│   ├── Cargo.toml
│   └── src/main.rs
├── vllm-launcher/             # vLLM launcher with profiles (section 4.18)
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs
│       └── profile_selector.rs
├── net-guard/                 # nftables & SOCKS5 management (section 4.8)
│   ├── Cargo.toml
│   └── src/main.rs
├── sandbox-launcher/          # Kata Containers launcher (section 4.6)
│   ├── Cargo.toml
│   └── src/main.rs
├── isolationd/                # Isolation Control Plane (section 4.17)
│   ├── Cargo.toml
│   └── src/main.rs
├── telemetryd/                # Telemetry collection and storage (section 6.6)
│   ├── Cargo.toml
│   └── src/main.rs
├── evolutiond/                # Genetic evolution engine (section 6.5)
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs
│       ├── population.rs
│       ├── fitness.rs
│       ├── llm_mutator.rs
│       └── hot_reload.rs
├── c2-router/                 # Multi‑Channel Stealth C2 (section 5.23.6)
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs
│       ├── channel.rs
│       ├── discord.rs
│       ├── dns.rs
│       └── webrtc.rs
├── hw-probe/                  # Hardware capability detection (P0-2)
│   ├── Cargo.toml
│   └── src/main.rs
└── scripts/                   # Helper scripts
    ├── generate_bom.py
    ├── extract_glossary.py
    └── verify_artifacts.sh
```

## K.4. Key Dependencies (from Cargo.lock)
The table below lists the main direct workspace dependencies with versions pinned in `Cargo.lock`
as of 2026‑04‑20.

| Crate            | Version        | Purpose                                          | License          |
| :--------------- | :------------- | :----------------------------------------------- | :--------------- |
| tokio            | 1.41.0         | Async runtime                                    | MIT              |
| reqwest          | 0.12.9         | HTTP client for APIs                             | MIT/Apache-2.0   |
| sled             | 0.34.7         | Embedded key‑value DB for telemetry              | Apache-2.0       |
| pqc-kyber        | 0.2.1          | Post‑quantum key encapsulation (Kyber‑1024)      | MIT/Apache-2.0   |
| pqc-dilithium    | 0.1.0          | Post‑quantum signatures (Dilithium5)             | MIT/Apache-2.0   |
| aes-gcm          | 0.10.3         | Authenticated encryption (AES‑256‑GCM)           | MIT/Apache-2.0   |
| ed25519-dalek    | 2.1.1          | Ed25519 signatures                               | BSD-3-Clause     |
| blake3           | 1.5.3          | Cryptographic hashing                            | CC0-1.0 / Apache-2.0 |
| serde / serde_json | 1.0.210 / 1.0.128 | Serialization/deserialization                 | MIT/Apache-2.0   |
| syn / quote      | 2.0.87 / 1.0.37 | Rust AST manipulation (for mutations)           | MIT/Apache-2.0   |
| candle-core      | 0.6.0          | Local inference of small models (quality predictor) | MIT/Apache-2.0 |
| libloading       | 0.8.5          | Dynamic library loading (hot‑reload)             | ISC              |
| matchbox-socket  | 0.13.2         | WebRTC P2P mesh                                  | MIT/Apache-2.0   |
| libp2p           | 0.54.1         | Peer‑to‑peer networking (gossip, Kademlia)       | MIT              |
| ipfs-api         | 0.17.1         | IPFS client                                      | MIT/Apache-2.0   |
| nftables         | 0.5.0          | nftables rule management                         | MIT              |
| sysinfo          | 0.31.4         | System information gathering (CPU, memory, processes) | MIT          |
| tokio-serial     | 5.4.4          | UART support (for watchdog)                      | MIT              |
| clap             | 4.5.20         | Command‑line argument parsing                    | MIT/Apache-2.0   |
| tracing / tracing-subscriber | 0.1.41 / 0.3.19 | Structured logging                         | MIT              |
| z3 (z3-sys)      | 0.13.0         | SMT solver (formal verification)                 | MIT              |

The full dependency list (including transitive dependencies) is available in the artifact `QmCoreToolsCargoLockV2`
(a separate `Cargo.lock` file).

## K.5. Minimum Supported Rust Version (MSRV)
The workspace requires Rust version 1.85.0 (edition 2024) or newer. The version is pinned
in the `rust-toolchain.toml` file:

```toml
[toolchain]
channel = "1.85.0"
components = ["rustfmt", "clippy"]
```

Using a fixed version guarantees build reproducibility and avoids problems with unstable language
features.

## K.6. Build and Installation
Full release build:

```bash
cd core-tools
cargo build --release --locked
```

The `--locked` flag ensures that exactly the versions of dependencies recorded in `Cargo.lock`
are used.

Installing binaries:

```bash
sudo cp target/release/{watchdogd,vllm-launcher,net-guard,sandbox-launcher,isolationd,telemetryd,evolutiond,c2-router,hw-probe} /usr/local/bin/
```

Integrity check of compiled binaries:  
Each release binary has a corresponding artifact with a hash in IPFS (see Appendix M).
You can compare the hash of a locally built file with the reference:

```bash
sha256sum /usr/local/bin/watchdogd
# Compare with the hash from artifact QmWatchdogdBinaryV2
```

## K.7. Dependency Report Generation
The script `cargo_deps_report.py` (CID `QmCargoDepsReportV1`) automatically extracts the dependency
list from `Cargo.lock` and generates a table in Markdown or JSON format.

Run:
```bash
ipfs get QmCargoDepsReportV1 -o cargo_deps_report.py
python cargo_deps_report.py --manifest-path core-tools/Cargo.toml --output deps.md
```

This script is used to update this appendix when a new document version is released.

## K.8. Dependency Security Audit
Before each release, a dependency audit is performed using `cargo audit` and `cargo deny`.
Audit results are saved in artifact `QmCargoAuditV2` and must show no known vulnerabilities
(RUSTSEC) for all crates in use.

```bash
cargo audit --deny warnings
cargo deny check
```

## K.9. Relationship with Other Sections
- 4.15 Quick‑Start Command Reference – build commands.
- 4.18 Configuration Profiles – use of `vllm-launcher`.
- 6.5 Genetic Evolution Engine – `evolutiond` crate.
- Appendix A – `hw-probe` for generating `hardware_profile.json`.

## K.10. Change History
| Artifact version | Date       | Changes                                                               | CID                      |
| :--------------- | :--------- | :-------------------------------------------------------------------- | :----------------------- |
| V1               | 2026-01-15 | Initial workspace (watchdogd, vllm-launcher, net-guard)               | `QmCoreToolsWorkspaceV1` |
| V2 (current)     | 2026-04-20 | Added isolationd, evolutiond, c2-router, hw-probe; updated dependencies | `QmCoreToolsWorkspaceV2` |
```