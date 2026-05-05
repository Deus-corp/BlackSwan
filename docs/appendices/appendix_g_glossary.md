# Appendix G – Machine-Readable Glossary (glossary.yaml)

**Purpose:** Provide a glossary in YAML format for automated processing, documentation generation, and link validation. The human-readable version is in [docs/glossary.md](Glossary.md).

---

## Current Artifact

| Field              | Value                                                     |
| :----------------- | :-------------------------------------------------------- |
| **CID (IPFS)**     | `QmGlossaryV4` (will be updated after merging)            |
| **BLAKE3 hash**    | `a9b8c7d6...`                                             |
| **File name**      | `glossary.yaml`                                           |
| **Schema version** | `3.1`                                                     |
| **Generation date**| 2026-04-26                                                |
| **Signature**      | `ed25519:...`                                             |

Download:
```bash
ipfs get QmGlossaryV4 -o glossary.yaml
```

---

## YAML Structure

The file contains an array of entries. Each entry is an object with fields:

- `term`: string – the term name.
- `definition`: string – the definition.
- `category`: string – one of the glossary categories (see below).
- `introduced_in`: string – the document/section where it was first defined.
- `related_terms`: list[string] – related terms.
- `aliases`: list[string] – alternative names.
- `source_files`: list[string] – paths to source code files where it is used.

Example:

```yaml
- term: "AWQ"
  definition: "Activation-aware Weight Quantization – an LLM quantization method that preserves accuracy by considering activation distributions."
  category: "Quantization"
  introduced_in: "Hardware_Isolation.md"
  related_terms: ["GPTQ", "GGUF"]
  aliases: []
  source_files: ["vllm_launcher/src/quantization.rs"]
```

---

## Categories

List of allowed categories (corresponds to sections of the human-readable glossary):

- System & Architecture
- Memory & Knowledge
- Economics & Finance
- Security & Stealth
- Verification & Evolution
- Motivation & Social
- Species
- Phases & States
- Hardware
- Distributed Systems
- Metrics & Criteria

---

## Automatic Generation

### Extraction from Source Code

The glossary can be populated from annotations in Rust/Python comments:

```
/// TERM: CRDT
/// DEFINITION: Conflict-free Replicated Data Type ...
/// CATEGORY: Distributed Systems
/// INTRODUCED_IN: CRDT_Gossip_and_D2BFT.md
```

Script `extract_glossary.py` (available as artifact `QmExtractGlossaryV2`):

```bash
ipfs get QmExtractGlossaryV2 -o extract_glossary.py
python extract_glossary.py --repo ~/BlackSwan --output glossary.yaml
```

The script collects annotations, merges them with the base `glossary.yaml`, and generates an updated file.

## Validation

Before publication, the following is checked:

- No duplicates.
- Compliance with the `glossary.schema.json` schema (CID `QmGlossarySchemaV1`).
- Presence of all terms mentioned in the documentation (via cross-reference link analysis).

---

## Integration with Documentation

- Human-readable glossary: `00_Manifesto/Glossary.md` – the primary reading location.
- Integrity check: CI can compare `glossary.yaml` with definitions in the manifest.

---

## Change History

| Version | Date       | Changes                                                      |
| :------ | :--------- | :----------------------------------------------------------- |
| V3      | 2026-04-20 | Complete rework, generation from code                        |
| V4      | 2026-04-26 | Merged with manifest glossary; single source of truth        |