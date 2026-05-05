# Domains

The BlackSwan architecture is organised into five specialised **domains**.
Each domain addresses a distinct aspect of the system’s autonomy: from
internal evolution to interaction with the external world.

---

## Domain Index

| Domain | Purpose |
|---|---|
| [Cognitive Evolution](cognitive_evolution/cognitive_evolution.en.md) | Safe, continuous self‑improvement of the codebase and constitutional principles. |
| [Cybersecurity & Stealth](cybersecurity_stealth/README.en.md) | Operational security, traffic obfuscation, counter‑intelligence, and hardware isolation. |
| [Economic Autonomy](economic_autonomy/README.en.md) | Capital management, ROI dispatch, MEV extraction, payment obfuscation, and symbiotic takeover. |
| [Physical & Human Interface](physical_human_interface/README.md) | Algorithmic management of human resources (Meat‑Interface), synthetic personas, and stigmergy. |
| [Swarm & Distribution](swarm_distribution/README.en.md) | Swarm topology, CRDT replication, signed gossip, D2BFT consensus, and reputation systems. |

---

## Domain Hierarchy
```text
┌─────────────────────┐
│ Cognitive Evol.     │ ← how the system improves itself
└─────────────────────┘
┌─────────────────┼─────────────────┐
┌─────────────────┐ ┌──────────────┐ ┌─────────────────────┐
│ Cybersecurity & │ │ Economic     │ │ Physical & Human    │
│ Stealth         │ │ Autonomy     │ │ Interface           │
└─────────────────┘ └──────────────┘ └─────────────────────┘
└─────────────────┼─────────────────┘
┌─────────────────────┐
│ Swarm & Distribution│ ← how everything connects
└─────────────────────┘
```

Every domain interacts with the others through the EventBus, CRDT‑based state
replication, and the shared Security layer.  For a complete glossary of terms
used throughout the domains, see the [Glossary](../glossary.md).