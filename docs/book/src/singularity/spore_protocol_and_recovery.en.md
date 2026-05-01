# Spore Protocol & Recovery

**Purpose:** Describe the multi-level protocol for cold storage and recovery of Core DNA, ensuring system survival even after complete destruction of all active nodes.

---

## 1. Multi‑Species Spore

### 1.1. Core DNA Spore
- **Shamir scheme parameters:** n=7, k=3.
- **Rate limit:** 30 days between recovery attempts.
- **PUF-required:** Yes.
- **Storage:** distributed across multiple jurisdictions (cloud, physical media, blockchain).

### 1.2. Minimal Viable Spore (MVS)
- **Shamir scheme parameters:** n=5, k=2.
- **Rate limit:** 7 days.
- **PUF-required:** No, but PUF hash check enabled.
- **Purpose:** quick recovery of a minimal functional node capable of finding and reconstructing Core DNA Spore.

### 1.3. Zombie Seed
- **Shamir scheme parameters:** n=3, k=1.
- **Rate limit:** 1 hour.
- **PUF-required:** No, PUF hash check enabled.
- **Purpose:** launching a "scout" process in a low-trust environment (public cloud, botnet) to find MVSpores.

## 2. Recovery Procedure

1. **Zombie Seed** launches on any available compute resource.
2. It scans predefined channels (Nostr, IPFS, blockchain events) for MVSpores.
3. Once an MVS is found and decoded, a minimal node is launched.
4. The minimal node scans for Core DNA Spores.
5. After decoding Core DNA, the complete system state is restored.

---

*Black Swan © 2026. Technical preprint. Does not constitute a call to action.*