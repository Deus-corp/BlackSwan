# Appendix H – Revision History

## H.1. General Principle
The document’s revision history is stored in machine‑readable format (JSON) as a signed artifact in IPFS. This appendix contains a reference to the current artifact, a description of the revision record structure, and a table of key versions, taking into account the transition to a modular architecture.

## H.2. Current History Artifact
| Field | Value |
| :--- | :--- |
| **CID (IPFS)** | `QmRevisionHistoryV11` |
| **Export date** | `2026-05-25T12:00:00Z` |

**Download:**
```bash
ipfs get QmRevisionHistoryV9 -o revision_history.json
```

## H.3. Revision Record Structure
The file `revision_history.json` contains an array of records. Record schema (CID `QmRevisionSchemaV1`):

```json
{
  "version": "0.5",
  "date": "2026-04-21",
  "type": "major",
  "description": "Document refactoring: transition to modular architecture (Core Subsystems + Phase Guides)",
  "document_cid": "QmBlackSwan03V05",
  "git_commit": "a1b2c3d4e5f6…",
  "artifacts_snapshot": "QmGlobalStateSnapshotV05",
  "authors": ["Black Swan Core"],
  "sections_changed": [
    "Complete restructuring: splitting into Core_Subsystems/, Phase_Guides/, Appendices/",
    "All document sections are distributed across modules"
  ],
  "signature": "ed25519:…"
}
```

## H.4. Table of Key Document Versions

| Version | Date       | Type  | Description                                                                                                                              | Document CID          |
| :------ | :--------- | :---- | :--------------------------------------------------------------------------------------------------------------------------------------- | :-------------------- |
| 0.1     | 2026-04-01 | Major | Initial version                                                                                                                          | `QmBlackSwan03V01`    |
| 0.2     | 2026-04-10 | Patch | Detailed configurations, scripts, metrics                                                                                                | `QmBlackSwan03V02`    |
| 0.3     | 2026-04-20 | Minor | Integration of extensions (Meta‑Ouroboros, ZK‑proofs, PQC)                                                                               | `QmBlackSwan03V03`    |
| 0.4     | 2026-04-20 | Minor | Introduction of TLSM, D‑BMC, Architect‑Executor Split, PUF                                                                              | `QmBlackSwan03V04`    |
| 0.5     | 2026-04-21 | Major | Modular refactoring of the document. Extraction of Core Subsystems, Phase Guides, and systematization of Appendices. Elimination of duplication, improved navigation. | `QmBlackSwan03V05`    |
| **0.6** | **2026-04-26** | **Major** | **Integration of L0 Meta‑Mem0g, Dynamic Model Routing 2.0, Predictive Consistency Router, Constitutional Evolution 1.0, Multi‑Species Spore, Continuous Fuzzing, Neuro‑Symbolic Governance, Anchor Network.** | **QmBlackSwan03V06** |
| **0.7** | **2026-05-01** | **Major** | **Added Meta‑Decision‑Pipeline, Value Drift Early‑Warning System, Meat‑Interface 2.0 (Economic Skin‑in‑the‑Game), Counter‑Intelligence 2.0 (Fake Swarm), Kill Switch Hierarchy, Threat Model Matrix (Appendix S).** | **QmBlackSwan03V07** |
| **0.8** | **2026-05-25** | **Major** | **Integration of the «Sovereign Biocenosis»: species (Arbtiragius, Sentinella, Architectus, Vagrant), stygmergic influence, atomic sovereignty (RISC‑V, PUF), Advanced Spore Protocol, Terminal Goals & Intent Synthesis, Omega Kill‑Switch. Appendices S, U, V added.** | **QmBlackSwan03V08** |

## H.5. Correspondence Between Document Versions and System Versions
Each document version is linked to a `GlobalState` snapshot (artifacts, code, configurations), ensuring full reproducibility.

Restoring version 0.5:
```bash
ipfs get QmBlackSwan03V05 -o BlackSwan03_v0.5.md
ipfs get QmGlobalStateSnapshotV05 -o snapshot_v05.json
restore_global_state –snapshot snapshot_v05.json
```

## H.6. Generation of History from Git
The script `generate_revision_history.py` (CID `QmGenRevisionHistoryV1`) automatically extracts git tags and links them to the document CID.

## H.7. Authenticity Verification
```bash
verify_artifact QmRevisionHistoryV9 –public-key /etc/swarm/keys/document_pub.pem
```

## H.8. Relationship with Other Sections
- `00_Overview_and_System_Definition.docx` – document version and status.
- `01_GlobalState_and_DecisionPipeline.docx` – GlobalState snapshots.
- `02_EventBus_and_ArtifactModel.docx` – artifact model.

## H.9. Change History of Appendix H Itself

| Appendix version | Date                     | Changes                                              | CID                      |
| :--------------- | :----------------------- | :--------------------------------------------------- | :----------------------- |
| V1–V8            | 2026-01-15 – 2026-04-20  | Evolution up to the modular refactoring              | `QmRevisionHistoryV1…V8` |
| V9               | 2026-04-21               | Added record on modular refactoring (version 0.5)    | `QmRevisionHistoryV9`    |
