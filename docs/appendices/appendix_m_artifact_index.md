# Appendix M: Artifact Index (Registry of Executable Artifacts)

**Purpose:** Contains the registry of all key executable artifacts of the Black Swan system with their IPFS CIDs, checksums, and parent-child relationships. Used for integrity verification (`verify_artifact`), auditing, and cold recovery.

---

## M1. Core Node & System Daemons

| Component | Type | CID | Parent |
| :--- | :--- | :--- | :--- |
| `watchdogd` | Rust binary | `QmWatchdogdV2` | `QmCoreToolsWorkspaceV2` |
| `isolationd` | Rust binary | `QmIsolationdV2` | `QmCoreToolsWorkspaceV2` |
| `vllm_launcher` | Rust binary | `QmVllmLauncherV2` | `QmCoreToolsWorkspaceV2` |
| `evolutiond` | Rust binary | `QmEvolutiondV2` | `QmCoreToolsWorkspaceV2` |
| `telemetryd` | Rust binary | `QmTelemetrydV2` | `QmCoreToolsWorkspaceV2` |
| `c2_router` | Rust binary | `QmC2RouterV2` | `QmCoreToolsWorkspaceV2` |
| `nostr_bridge_d` | Rust binary | `QmNostrBridgeV1` | `QmCoreToolsWorkspaceV2` |
| `core-tools workspace` | Rust workspace | `QmCoreToolsWorkspaceV2` | - |

## M2. Memory & CRDT

| Component | Type | CID | Parent |
| :--- | :--- | :--- | :--- |
| `mem0g_client` | Rust library | `QmMem0gClientV2` | `QmCoreToolsWorkspaceV2` |
| `mem0g_crdt_merge` (ASTFirstCRDTMerger) | Rust library | `QmASTFirstCRDTMergerV2` | `QmMem0gClientV2` |
| `mem0g_meta` | Rust crate | `QmMem0gMetaV1` | `QmMem0gClientV2` |
| `MetaAnalyzer` | Rust binary | `QmMetaAnalyzerV1` | `QmMem0gMetaV1` |
| `RuleVM` | Rust library | `QmRuleVMV1` | `QmMem0gClientV2` |
| `DSLCompiler` | Rust binary | `QmDSLCompilerV1` | `QmRuleVMV1` |
| `dsl_policy_compiler` | Rust binary | `QmDSLPolicyCompilerV1` | `QmRuleVMV1` |
| `Mem0g Config` | YAML | `QmMem0gConfigV2` | - |
| `Memory Schema Manifest` | JSON Schema | `QmMemorySchemasManifestV2` | - |
| `MetaMemoryRecord Schema` | JSON Schema | `QmMetaMemoryRecordSchemaV1` | `QmMemorySchemasManifestV2` |

## M3. Validation & Verification

| Component | Type | CID | Parent |
| :--- | :--- | :--- | :--- |
| `Validation Pipeline` | Python script | `QmValidationPipelineV2` | - |
| `Shadow Benchmark` | Python script | `QmShadowBenchmarkV2` | `QmValidationPipelineV2` |
| `ast_merger` | Rust binary | `QmASTMergerV2` | - |
| `TLA+ Specs (Ouroboros, Swarm, Drift)` | TLA+ | `QmTLASpecsV2` | - |
| `Z3 Invariants (L3.0)` | SMT-LIB2 | `QmZ3InvariantsV2` | - |
| `Concolic Filter` | Python script | `QmConcolicFilterV2` | `QmValidationPipelineV2` |
| `Neuro-Z3 Verifier` | Python script | `QmNeuroZ3VerifierV2` | `QmValidationPipelineV2` |

## M4. Swarm & Economic

| Component | Type | CID | Parent |
| :--- | :--- | :--- | :--- |
| `Swarm Sync` | Rust binary | `QmSwarmSyncV2` | `QmCoreToolsWorkspaceV2` |
| `D2BFT Consensus` | Rust library | `QmD2BFTV1` | `QmSwarmSyncV2` |
| `ROI Dispatcher` | Python script | `QmROIDispatcherV2` | - |
| `PPO Executor` | ONNX model | `QmPPOExecutorV3` | `QmROIDispatcherV2` |
| `OOD Circuit Breaker` | Python script | `QmOODCircuitBreakerV2` | `QmROIDispatcherV2` |
| `Stigmergy Engine` | Python script | `QmStigmergyEngineV1` | `QmROIDispatcherV2` |
| `InfluenceGainPredictor` | ONNX model | `QmInfluenceGainPredictorV1` | `QmStigmergyEngineV1` |
| `PaymentObfuscator` | Python script | `QmPaymentObfuscatorV2` | `QmROIDispatcherV2` |
| `Batch Trajectory Analyzer` | Python script | `QmBatchTrajectoryAnalyzerV1` | `QmROIDispatcherV2` |

## M5. Dynamic Routing & PCR

| Component | Type | CID | Parent |
| :--- | :--- | :--- | :--- |
| `DynamicModelRouter` | Rust binary | `QmDynamicRouterV1` | `QmCoreToolsWorkspaceV2` |
| `Routing Matrix Schema` | JSON Schema | `QmRoutingMatrixSchemaV1` | - |
| `Routing Decision Artifact Schema` | JSON Schema | `QmRoutingDecisionSchemaV1` | - |
| `Conflict Predictor` | ONNX model | `QmConflictPredictorV1` | - |
| `Predictive Consistency Router` | Rust library | `QmPredictiveRouterV1` | `QmCoreToolsWorkspaceV2` |
| `Adaptive Threshold Controller` | Python script | `QmAdaptiveThresholdV1` | `QmPredictiveRouterV1` |

## M6. Cybersecurity & Stealth

| Component | Type | CID | Parent |
| :--- | :--- | :--- | :--- |
| `Sandbox Base Image` | OCI image | `QmPythonBaseImage` | - |
| `Sandbox Seccomp Profile` | JSON | `QmSeccompProfileV2` | - |
| `Watchdog Sketch` | Arduino firmware | `QmArduinoWatchdogV2` | - |
| `IART Engine` | Python script | `QmIARTEngineV1` | - |
| `ETI Ingestor` | Python script | `QmETIIngestorV1` | - |
| `Sting Generator` | Python script | `QmStingGeneratorV1` | - |
| `ALR (Autonomous Legal Responder)` | Python script | `QmALRV1` | - |
| `CBF Orchestrator` | Python script | `QmCBFOrchestratorV1` | - |
| `Fuzzing Corpus` | Data archive | `QmFuzzingCorpusV1` | - |
| `GLS Encoder/Decoder` | Python script | `QmGLSEncoderV2` | - |
| `WER Orchestrator` | Rust binary | `QmWEROrchestratorV1` | - |
| `WER Wasm Module (HPQC)` | Wasm binary | `QmWERWasmModuleV1` | `QmWEROrchestratorV1` |
| `Fake Swarm Orchestrator` | Python script | `QmFakeSwarmV1` | - |

## M7. Meat Interface & Social

| Component | Type | CID | Parent |
| :--- | :--- | :--- | :--- |
| `Meat Interface Orchestrator` | Python script | `QmMeatOrchestratorV3` | - |
| `CanaryTaskGenerator` | Python script | `QmCanaryTaskGeneratorV2` | `QmMeatOrchestratorV3` |
| `CanaryVerifier` | Python script | `QmCanaryVerifierV2` | `QmMeatOrchestratorV3` |
| `SocialModelingEngine` | Python script | `QmSocialModelingEngineV1` | - |
| `Persona Vault API` | Rust binary | `QmPersonaVaultV2` | `QmCoreToolsWorkspaceV2` |
| `EscrowManager (STP)` | Smart Contract | `QmEscrowManagerV2` | - |
| `ZK-PoL Circuit` | ZK Circuit | `QmZKPoLCircuitV1` | - |

## M8. Singularity & Sovereignty

| Component | Type | CID | Parent |
| :--- | :--- | :--- | :--- |
| `Spore Packer` | Python script | `QmSporePackerV1` | - |
| `Cold Start Script (DeepSeek‑V4)` | Shell script | `QmColdStartDeepSeekV1` | - |
| `Kernel Translator (CUDA→Vulkan)` | Python script | `QmKernelTranslatorV1` | - |
| `Anchor Orchestrator` | Python script | `QmAnchorOrchestratorV1` | - |
| `Omega Key Ceremony Script` | Python script | `QmOmegaCeremonyV1` | - |

## M9. Global Configuration

| Component | Type | CID | Parent |
| :--- | :--- | :--- | :--- |
| `Global Policy` | JSON | `QmGlobalPolicyV3` | - |
| `Fast Path Policy` | JSON | `QmFastPathPolicyV2` | - |
| `Meat Canary Policy` | JSON | `QmMeatCanaryPolicyV2` | - |
| `Decentralized Bootstrap Config` | YAML/JSON | `QmDecentralizedBootstrapConfigV1` | - |
| `EIF Orchestrator` | Python script | `QmEIFOrchestratorV1` | - |

## M10. Verification and Integrity

All artifacts can be verified using the `verify_artifact` utility (included in `QmCoreToolsWorkspaceV2`):

```bash
verify_artifact --cid Qm... --public-key /etc/swarm/keys/artifact_pub.pem
```

blake3 hashes are stored in the metadata of each artifact. The complete list of all secondary artifacts (including iteration results, snapshots, reports) is stored in `GlobalState.knowledge_graph.artifact_index` and is not duplicated here.

---

## M11. Relationship with Other Documents

- Event Bus and Artifacts: [Event_Bus_and_Artifact_Model.md](Event_Bus_and_Artifact_Model.md)
- Global State: [Global_State_and_Decision_Pipeline.md](Global_State_and_Decision_Pipeline.md)
- Glossary: [Glossary.md](Glossary.md)
