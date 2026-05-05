# Appendix Z — Proof Tree Specification
## Z.1. Purpose
Definition of the format and validation rules for logical derivation trees
used in Constitutional Debate 2.0 to prove
the compatibility of proposed L3.1‑invariants with L3.0‑axioms.
## Z.2. Proof Tree Structure
The tree is represented as a JSON object with a recursive structure.
### Z.2.1. Tree Node
| Field | Type | Description |
| :--- | :--- | :--- |
| `node_id` | string | Unique identifier of the node |
| `statement` | string | Logical assertion (in SMT‑LIB2 or natural language) |
| `rule` | string | Applied inference rule (e.g., `modus_ponens`, `forall_intro`) |
| `children` | array[string] | List of `node_id`s of child nodes on which the derivation is based |
| `z3_verified` | boolean | Flag indicating successful verification of the node by Z3 |
| `z3_model` | object | (Optional) Z3 model confirming the assertion |
### Z.2.2. Root Node
The root node contains the final assertion that must be proved.
All leaves must be either L3.0 axioms or previously proved
lemmas from Mem0g L2.
## Z.3. Inference Rules
Supported rules (minimal set):
| Rule | Description |
| :--- | :--- |
| `axiom` | The assertion is an L3.0 axiom |
| `modus_ponens` | From A and A → B derive B |
| `forall_intro` | Introduction of the universal quantifier |
| `exists_elim` | Elimination of the existential quantifier |
| `conj_intro` | Introduction of conjunction |
| `disj_elim` | Elimination of disjunction |
| `lemma` | Reference to a previously proved lemma (CID) |
## Z.4. Tree Validation
1. Structural integrity check: all `children` refer to
   existing nodes, no cycles.
2. For each node, verify that its `statement` logically follows
   from the `statements` of its child nodes according to the specified `rule`.
3. Multi‑Solver (Z3, CVC4, Yices) confirms the logical consequence.
4. Concolic Filtering checks that the assertion is not a
   trivial tautology.
## Z.5. Storage
Trees are stored in IPFS as artifacts of type `ProofTree`. A reference to the
tree is included in the `ConstitutionalPrinciple` in Mem0g L2.
## Z.6. Change History
| Version | Date | Changes |
| :--- | :--- | :--- |
| V1 | 2026-06-20 | Initial specification for v2.0 |