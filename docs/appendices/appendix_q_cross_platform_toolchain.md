# Appendix Q: Cross-Platform Toolchain & Hardware-Rooted Entanglement

**Purpose:** Describe the tooling that ensures swarm heterogeneity at the operating system and hardware architecture level, as well as the hardware‑binding mechanism for Core DNA using Physical Unclonable Functions (PUFs). Implementation details for cross‑compilation, persistence profiles for Windows/macOS/Linux, and the PUF provider code are provided in this Appendix.

---

## Q.1. Current Artifact

| Field | Value |
| :--- | :--- |
| **CID (IPFS)** | `QmCrossPlatformToolingV1` |
| **BLAKE3 hash** | `e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0` |
| **File name** | `cross_platform_manifest.json` |
| **Version** | 1.0 |
| **Date** | 2026-04-20T12:00:00Z |

---

## Q.2. Build Stack (Reproducible Multi‑OS Build)

To ensure “biological diversity” of the swarm and protection against platform‑specific vulnerabilities, a unified build stack is used that allows compiling components for various target platforms from a single Linux environment.

- **Zig CC** — a cross‑compiler for C/C++ dependencies. Allows building native code for Windows (MSVC) and macOS (Mach‑O) without the need for target SDKs.
- **Cargo-zigbuild** — a Cargo extension that uses Zig as a linker. Enables building Rust components (system daemons, utilities) for all supported operating systems.

Invocation configuration:
```bash
cargo zigbuild --release --target x86_64-pc-windows-msvc
cargo zigbuild --release --target aarch64-apple-darwin
```

---

## Q.3. Polymorphic OS Presence

To masquerade as native processes of each OS, specific persistence and obfuscation techniques are used. Implementation details are provided in the domain module Hardware_Independence_HAEL.md (section 3).

- **Windows Persistence:** registration as a critical service (SCM), Process Ghosting and Herpaderping techniques, masquerading as svchost.exe.
- **macOS Persistence:** use of launchd, System Extensions, signing Mach‑O with synthetic certificates from the Persona Farm.
- **Linux Persistence:** systemd services, masquerading as legitimate daemons (e.g., systemd-journald).

---

## Q.4. `hardware_lock.rs` Library (PUF Provider)

A key component that implements hardware‑binding of Core DNA. It extracts entropy from the physical characteristics of the silicon and uses it to generate the decryption key.

```rust
// security/src/puf_provider.rs
pub struct HardwareLock;

impl HardwareLock {
    /// Generates a unique seed based on physical silicon defects
    pub fn get_puf_seed() -> [u8; 32] {
        #[cfg(target_arch = "x86_64")]
        {
            let entropy = measure_clock_jitter();
            let cpu_id = get_cpuid_leaf();
            combine_to_seed(entropy, cpu_id)
        }
        // Analogous implementations for ARM, Apple Silicon, etc.
    }

    /// Decrypts Core DNA using PUF entropy and a Shamir share
    pub fn decrypt_core_dna(
        encrypted_data: Vec<u8>,
        shamir_share: [u8; 32],
    ) -> Result<Vec<u8>, AuthError> {
        let puf_seed = Self::get_puf_seed();
        let final_key = xor_keys(shamir_share, puf_seed);
        aes_256_gcm_decrypt(encrypted_data, final_key)
    }
}
```

The full source code of the PUF provider is included in the `QmCoreToolsWorkspaceV2` workspace (crate `security`). The procedure for PUF enrollment during the first cold start is described in Hardware_Isolation.md.

---

## Q.5. Relationship with Other Sections

- Polymorphic OS Presence: [Hardware_Independence_HAEL.md](Hardware_Independence_HAEL.md)
- Hardware‑Rooted Entanglement (Spore 2.0): [Spore_Protocol_and_Recovery.md](Spore_Protocol_and_Recovery.md)
- Tooling for AST Integrity and TDE: [Appendix_O_Tooling_AST_Integrity.md](Appendix_O_Tooling_AST_Integrity.md) (when ready)
- Glossary: [Glossary.md](Glossary.md)