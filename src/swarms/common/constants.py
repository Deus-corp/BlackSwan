"""Shared runtime constants for BlackSwan swarms.

These constants are the single source of truth for common identifiers used
across multiple swarms and protocols. Import from here instead of defining
local copies.
"""

# ------------------------------------------------------------------
# Execution risk tiers (aligned with contracts.ExecutionRiskTier)
# ------------------------------------------------------------------
SAFE_LOCAL_EXECUTION = "safe_local_execution"
NETWORK_READ = "network_read"
TESTNET_EXTERNAL_WRITE = "testnet_external_write"
EXTERNAL_WRITE_STUB = "external_write_stub"
PRODUCTION_FINANCIAL_WRITE = "production_financial_write"
SYSTEM_DANGEROUS_STUB = "system_dangerous_stub"

# ------------------------------------------------------------------
# Coordination / evidence channels
# ------------------------------------------------------------------
COORDINATION_CHANNEL_CRDT_GENOMES = "crdt_genomes"
EVIDENCE_KIND_WEB_FETCH = "web_fetch"

# ------------------------------------------------------------------
# Memory record types (used by Explorer → Memory handoff)
# ------------------------------------------------------------------
MEMORY_RECORD_TYPE = "memory_record"
MEMORY_EVIDENCE_RECORD_KIND = "explorer_useful_evidence"
MEMORY_EVIDENCE_SCHEMA_VERSION = "1.0"

# ------------------------------------------------------------------
# Commonly used quality thresholds
# ------------------------------------------------------------------
MIN_MEMORY_HANDOFF_CONFIDENCE = 0.50
MIN_MEMORY_HANDOFF_SOURCE_SCORE = 0.65
MIN_MEMORY_HANDOFF_RELEVANCE_SCORE = 0.60
MIN_MEMORY_HANDOFF_CONTENT_PREVIEW_CHARS = 80