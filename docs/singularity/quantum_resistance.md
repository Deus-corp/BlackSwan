# Quantum Resistance (Quantum-Resistant Core)

**Purpose:** Ensure long-term cryptographic security of the system against the threat posed by large-scale quantum computing (the “Harvest Now, Decrypt Later” attack). This module describes the migration to post‑quantum algorithms (Kyber‑1024, Dilithium‑5), hybrid signatures during the transition period, key rotation protocols, and hardware‑binding strengthening via Quantum‑Resistant Optical PUF.

---

## 1. Threat and Rationale

Classical cryptography (Ed25519, X25519, AES‑GCM) is vulnerable to attacks based on Shor’s algorithm. An adversary recording encrypted traffic today will be able to decrypt it in 5–15 years once a sufficiently powerful quantum computer emerges. For a system whose secrets (Core DNA, control keys, L3 invariants) must remain undisclosed for decades, migration to post‑quantum cryptography (PQC) is mandatory.

---

## 2. Post-Quantum Algorithms and Hybrid Mode

### 2.1. Selected Standards (NIST IR 8547)

- **KEM (Key Encapsulation):** **Kyber‑1024** for session‑key encapsulation. Replaces X25519 in key‑agreement protocols.
- **Signatures:** **Dilithium‑5** for message authentication and artifact signing. Replaces Ed25519 for critical operations.
- **Hybrid mode:** During the transition period, dual signature/encapsulation is used: classical + post‑quantum. This ensures compatibility with nodes that have not yet completed migration and provides protection against unknown attacks on the new algorithms.

### 2.2. Migration States
```text
CLASSIC → HYBRID → PQ_ONLY
│
└──→ ROLLBACK (temporary)
```

| State | Description | Actions |
| :--- | :--- | :--- |
| **CLASSIC** | Only Ed25519 / X25519 | Only classical signatures accepted. |
| **HYBRID** | Parallel use | Both signatures verified; a hybrid (classical + Dilithium) is generated. |
| **PQ_ONLY** | Only Dilithium‑5 / Kyber‑1024 | Classical signatures are rejected. |
| **ROLLBACK** | Temporary fallback | Activated when a critical vulnerability in PQC is detected. |

---

## 3. Key Rotation and Lifecycle

- **Classical keys:** Rotation every 30 days (legacy policy).
- **Post‑quantum keys:** Rotation every 90 days (larger size and higher computational cost).
- **Hybrid keys:** Rotation synchronized with classical keys (every 30 days); a fresh Kyber‑1024 pair is generated at each rotation.
- **Known Answer Tests (KATs):** Deterministic conformance tests against NIST reference vectors are performed every time a key is generated.

---

## 4. Integration with WER 2.0 and HPQC

Wasm Ephemeral Relays 2.0 (WER) use a hybrid post‑quantum scheme (HPQC) to protect session keys. Protocol:

1. Core Node and Relay perform a hybrid key exchange: X25519 + Kyber‑768 (or Kyber‑1024 for channels with sensitivity ≥ 4).
2. The session key is encrypted via Kyber KEM wrapping.
3. Key rotation every 15 minutes with Perfect Forward Secrecy.
4. Even if the classical part is compromised, an attacker cannot decrypt the traffic without breaking the lattice‑based primitive.

---

## 5. Quantum‑Resistant Optical PUF

To strengthen the hardware binding of `Core DNA` against quantum attacks on classical PUFs (SRAM, clock skew), an optical PUF is introduced:

- **Principle:** A laser beam scatters off the microstructure of a transparent chip. The resulting interference pattern is unique to each instance and mathematically unpredictable.
- **Quantum resistance:** The optical PUF is based on scattering physics, not on computational complexity. It is not vulnerable to Shor’s algorithm.
- **Integration:** The optical PUF is used as an additional entropy source in the `K_dna` generation formula.

---

## 6. Configuration

```json
{
  "quantum_resistance": {
    "migration_state": "HYBRID",
    "pqc_algorithms": {
      "kem": "kyber-1024",
      "signature": "dilithium-5"
    },
    "hybrid_mode": true,
    "key_rotation": {
      "classic_days": 30,
      "pqc_days": 90
    },
    "optical_puf": {
      "enabled": true,
      "integration": "k_dna_entropy_source"
    }
  }
}
```

## 7. Success Criteria

Metric	Target Value
HNDL Resistance	100% of key traffic protected by hybrid PQC
Migration Completion	All Core Nodes in PQ_ONLY state by 2028
Optical PUF False Rejection	< 0.5%
Key Rotation Compliance	100% on schedule

## 8. Relationship with Other Documents

WER 2.0 and HPQC: Stealth_and_C2.md
Hardware binding (PUF): Hardware_Independence_HAEL.md
Singularity criteria: Singularity_Criteria.md
Security: Operational_Security_IART.md