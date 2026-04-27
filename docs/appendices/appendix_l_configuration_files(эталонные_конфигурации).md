# Appendix L: Configuration Files (Эталонные конфигурации)

**Назначение:** Содержит эталонные конфигурационные файлы, управляющие поведением системы Black Swan. Включает единый `global_policy.json`, а также профильные конфигурации для Fast Path, Meat Canary, Dynamic Routing и Evolution. Все параметры, упомянутые в документации, собраны здесь.

---

## L1. global_policy.json (Основной файл политик)

```json
{
  "version": "2.0",
  "last_updated": "2026-04-26",

  "meta_decision_pipeline": {
    "enabled": true,
    "analysis_interval_hours": 6,
    "shadow_test_duration_days": 7,
    "promotion_quorum": 3,
    "min_improvement_threshold": 0.03
  },

  "predictive_routing": {
    "enabled": true,
    "model_path": "/var/lib/swarm/models/conflict_predictor.onnx",
    "base_threshold": 0.65,
    "adaptive_threshold_enabled": true,
    "min_precision": 0.80
  },

  "dynamic_routing": {
    "enabled": true,
    "fallback_policy": {
      "node_type": "edge",
      "species_mask": "vagrant",
      "expert_percent": 20,
      "quant": "awq_4bit",
      "spec_tokens": 6
    },
    "cache_ttl_sec": 300,
    "shadow_experiment_rate": 0.10
  },

  "memory": {
    "l0_enabled": true,
    "l0_budget_percent": 5,
    "l0_min_experiment_days": 7,
    "l0_promotion_quorum": 3,
    "l0_constitutional_debate_required": true,
    "jepa_layer": {
      "enabled": true,
      "encoder_species_mask": "vagrant",
      "latent_dim": 1536,
      "reencode_interval_hours": 24,
      "min_compression_ratio": 15,
      "min_link_prediction_auc": 0.85
    },
    "l2_compression": {
      "dsl_enabled": true,
      "max_rules_per_node": 200,
      "compilation_retries": 3
    }
  },

  "intrinsic_motivation": {
    "enabled": false,
    "shadow_mode": true,
    "survival_weight": 0.6,
    "exploration_weight": 0.2,
    "capital_weight": 0.2,
    "curiosity_loop_interval_sec": 3600,
    "min_surprise_threshold": 0.15,
    "max_exploration_resource_share": 0.05,
    "survival_objective": {
      "lambda": 0.15,
      "min_p_liveness": 0.999
    },
    "curiosity_tiered_filter": {
      "enabled": true,
      "tier1_species_mask": "vagrant",
      "tier2_species_mask": "architectus",
      "tier1_threshold": 0.12,
      "max_tier2_batch": 100,
      "recency_decay_days": 7
    },
    "adaptive_weights": {
      "enabled": false,
      "agent_model_cid": "QmMetaPOMDPAgentV1",
      "belief_update_interval_sec": 3600,
      "min_exploration_weight": 0.1
    }
  },

  "social_modeling": {
    "enabled": false,
    "shadow_mode": true,
    "ab_test_sample_rate": 0.1,
    "max_social_exploit_budget_percent": 2,
    "min_suspicion_threshold": 0.3,
    "hypothesis_confidence_threshold": 0.75,
    "statistical_significance_level": 0.05,
    "metrics_retention_days": 90,
    "persona_rotation_after_experiments": 3
  },

  "economic": {
    "max_risk_per_trade": 0.02,
    "sharpe_threshold": 0.6,
    "phi_llm": 0.25,
    "convexity_bonus": {
      "enabled": true,
      "weight": 0.15,
      "capital_allocation_max": 0.05
    },
    "ood_circuit_breaker": {
      "enabled": true,
      "threshold": 0.75,
      "statistical_weight": 0.4,
      "embedding_weight": 0.4,
      "prediction_error_weight": 0.2,
      "cooldown_minutes": 60
    },
    "policy_compression": {
      "mode": "dsl",
      "batch_interval_hours": 24,
      "min_trajectories": 1000,
      "max_rules_per_batch": 50,
      "shadow_validation_days": 7
    },
    "symbiotic_takeover": {
      "enabled": true,
      "max_capital_per_target": 0.05,
      "target_governance_share": 0.15
    }
  },

  "swarm_scheduler": {
    "fast_path": {
      "enabled": true,
      "max_latency_ms": 50,
      "audit_sample_rate": 0.1
    }
  },

  "consensus": {
    "protocol": "d2bft",
    "validator_count": 7,
    "leader_rotation_interval": 60,
    "view_change_timeout_ms": 3000,
    "max_byzantine_faults": 0.40
  },

  "reputation": {
    "decay_lambda": 0.1,
    "quarantine_reliability_threshold": 0.5,
    "quarantine_correctness_threshold": 0.7,
    "recovery_tasks_required": 10
  },

  "stealth": {
    "enable_host_monitoring": true,
    "edr_detection_threshold": "medium",
    "auto_destruct_on_debugger": true,
    "media_synthesis": {
      "provider": "deepseek-v4",
      "species_mask": "architectus",
      "stego_enabled": true,
      "max_payload_bytes": 256
    }
  },

  "stigmergy": {
    "enabled": true,
    "default_influence_weight": 0.3,
    "zero_profit_threshold": 0.7,
    "influence_gain_model": "QmInfluenceGainPredictorV1"
  },

  "counter_intelligence": {
    "fake_swarm_enabled": true,
    "fake_swarm_count": 5,
    "deception_level": "high",
    "auto_activate_on_threat": "critical",
    "orchestrator_cid": "QmFakeSwarmV1"
  },

  "counter_stigmergy": {
    "enabled": true,
    "anomaly_threshold": 0.65,
    "cross_source_weight": 0.4,
    "temporal_weight": 0.3,
    "persona_weight": 0.3,
    "auto_quarantine_hostile": true
  },

  "sting": {
    "enabled": true,
    "auto_respond_level": 1,
    "require_confirmation_for_level": [2, 3]
  },

  "kill_switch_hierarchy": {
    "enabled": true,
    "auto_escalate": true,
    "require_confirmation_for_level": [3, 4, 5],
    "dead_mans_switch_timeout_days": 30
  },

  "omega_protocol": {
    "enabled": false,
    "require_external_trigger": true,
    "shamir_threshold_k": 3,
    "shamir_total_n": 5,
    "min_drift_probability": 0.95
  },

  "cold_start": {
    "max_total_time_sec": 300,
    "watchdog_first_heartbeat_sec": 120,
    "gpu_detect_retries": 5,
    "sandbox_start_timeout_ms": 500
  },

  "hardware_transition": {
    "enabled": true,
    "target_fund_usd": 45000,
    "shadow_duration_days": 14,
    "cutover_confirmation_rounds": 3,
    "model_cid": "QmDeepSeekV4Weights",
    "api_shutdown_grace_period_days": 30
  },

  "species_experts": {
    "enabled": true,
    "base_model": "deepseek-v4",
    "expert_masks": {
      "arbiter": [0, 1, 2, "... (30% of 256)"],
      "sentinel": ["... (40% of 256)"],
      "architect": ["... (60% of 256)"],
      "vagrant": ["... (20% of 256)"]
    },
    "dynamic_activation": true
  },

  "meat_interface_v2": {
    "skin_in_the_game_enabled": true,
    "nft_burn_on_violation": true,
    "reputation_levels": [1, 5, 10, 25, 50, 100],
    "nft_contract_address": "0x..."
  },

  "meat_interface_v3": {
    "multimodal_enabled": true,
    "model": "deepseek-v4",
    "max_tokens_per_verification": 4096,
    "cache_verification_results": true
  },

  "persona_farm": {
    "enabled": true,
    "max_active_personas": 50,
    "growth_duration_months": 12,
    "rotation_after_experiments": 3
  },

  "legal_dao": {
    "enabled": true,
    "multisig_threshold": 3,
    "multisig_total": 5,
    "max_single_withdrawal_usd": 100000,
    "daily_withdrawal_limit_usd": 500000,
    "key_rotation_months": 6
  },

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
    }
  },

  "hardware_independence": {
    "hael_enabled": true,
    "jit_backends": ["cuda", "vulkan", "metal", "opencl", "riscv_vector"],
    "kernel_porting": {
      "enabled": true,
      "max_shadow_perf_drop": 0.20
    },
    "puf": {
      "enabled": true,
      "entropy_sources": ["sram", "clock_skew", "mem_latency"],
      "key_derivation": "sha3-512"
    }
  },

  "spore_protocol": {
    "multi_species": {
      "core_dna": {
        "shamir_n": 7,
        "shamir_k": 3,
        "rate_limit_days": 30,
        "puf_required": true
      },
      "mvs": {
        "shamir_n": 5,
        "shamir_k": 2,
        "rate_limit_days": 7,
        "puf_required": false,
        "puf_hash_check": true
      },
      "zombie": {
        "shamir_n": 3,
        "shamir_k": 1,
        "rate_limit_hours": 1,
        "puf_required": false,
        "puf_hash_check": true
      }
    },
    "time_lock": {
      "enabled": true,
      "core_dna_days": 30,
      "mvs_days": 7,
      "reset_interval_hours": 24,
      "min_compute_ratio": 1000
    },
    "dead_mans_switch": {
      "required_triggers": 2,
      "triggers": ["smart_contract", "nostr", "time_lock"]
    }
  },

  "anchor_network": {
    "enabled": true,
    "min_anchors_for_verification": 3,
    "beacon_interval_sec": 5,
    "key_rotation_days": 180,
    "compromise_detection": {
      "max_silence_minutes": 60,
      "max_location_drift_m": 100
    }
  },

  "continuous_fuzzing": {
    "enabled": true,
    "min_idle_cpu_percent": 70,
    "session_duration_minutes": 45,
    "max_sessions_per_day": 4,
    "corpus_cid": "QmFuzzingCorpusV1",
    "sanitizers": ["address", "leak", "undefined"],
    "module_priorities": {
      "isolationd": 1.0,
      "crdt_engine": 0.9,
      "roi_dispatcher": 0.8,
      "meat_orchestrator": 0.7,
      "evolutiond": 0.6
    }
  },

  "language_polyculture": {
    "enabled": false,
    "rotation_interval_days": 7,
    "target_languages": ["zig", "go"],
    "max_polyculture_nodes_percent": 20,
    "shadow_test_duration_hours": 24
  },

  "wer": {
    "version": "2.0",
    "enabled": true,
    "min_hops": 2,
    "platforms": ["cloudflare", "fastly", "fermyon"],
    "session_ttl_sec": 3600,
    "key_rotation_interval_sec": 900,
    "pqc_mode": "hybrid_kyber768_x25519",
    "padding_size_bytes": 2048
  },

  "validation": {
    "multimodal": {
      "enabled": true,
      "model": "deepseek-v4",
      "min_score": 0.85
    },
    "continuous_l3_check": {
      "enabled": true,
      "mode_by_species": {
        "architect": "full",
        "sentinel": "full",
        "arbiter": "delta",
        "vagrant": "periodic"
      },
      "cache_ttl_iterations": 50
    }
  },

  "verification": {
    "neuro_invariant_enabled": true,
    "concolic_filter": {
      "enabled": true,
      "engine": "angr",
      "max_time_sec": 5,
      "triviality_check": true
    }
  },

  "value_drift": {
    "enabled": true,
    "bayesian_threshold": 0.02,
    "early_warning_window_days": 30,
    "embedding_model": "deepseek-v4",
    "check_interval_hours": 24
  }
}
```

---

## L2. fast_path_policy.json (Политика Fast Path)

```json
{
  "domains": [
    {
      "name": "economic_executor_ppo",
      "max_kelly_fraction": 0.02,
      "max_cvar": 0.015,
      "routing": {
        "use_fast_cache": true,
        "max_latency_ms": 50
      }
    },
    {
      "name": "security_anomaly_response",
      "max_latency_ms": 100,
      "routing": {
        "use_fast_cache": true
      }
    }
  ],
  "post_audit": {
    "enabled": true,
    "sample_rate": 0.1,
    "anomaly_threshold": 0.05
  }
}
```

---

## L3. meat_canary_policy.json (Политика Meat Canary)

```json
{
  "injection_rate": 0.07,
  "auto_quarantine_threshold": 0.85,
  "canary_categories": {
    "photo_verification": {"weight": 0.4, "stake_range_usd": [50, 200]},
    "gps_tracking": {"weight": 0.3, "stake_range_usd": [100, 500]},
    "document_scan": {"weight": 0.2, "stake_range_usd": [75, 300]},
    "web_form": {"weight": 0.1, "stake_range_usd": [25, 100]}
  },
  "adversarial_templates": {
    "enabled": true,
    "source": "iart_red_team",
    "max_injection_rate": 0.02
  }
}
```

---

## L4. evolutiond.toml (Конфигурация генетического движка)

```toml
[population]
size = 10
elite_fraction = 0.25
crossover_rate = 0.7
mutation_rate = 0.3

[llm]
enabled = true
model = "deepseek-v4"
species_mask = "vagrant"
expert_percent = 20
context_size = 2048

[diversity]
enabled = true
warning_threshold = 0.15
critical_threshold = 0.08
check_interval_generations = 5
archive_size = 20
nes_forced_generations = 10

[open_endedness]
enabled = true
radical_bonus_max = 1.0
innovation_archive_size = 50
meta_innovation_interval_days = 30
meta_innovation_duration_days = 7
meta_innovation_resource_share = 0.20

[stepping_stones]
enabled = true
archive_path = "/var/lib/swarm/stepping_stones"
novelty_threshold = 0.85
min_complexity = 15
pfv_threshold = 0.3
archive_max_size = 500
recombination_rate = 0.1
init_population_ratio = 0.2

[champion_challenger]
shadow_duration_sec = 3600
promotion_quorum = 3
rollback_threshold_errors = 10
rollback_coherency_drop = 0.05

[telemetry]
db_path = "/var/lib/swarm/evolution_db"
```

---

## L5. Связь с другими документами

· Принципы проектирования: Design_Principles.md
· ADR-записи: Обоснования параметров в соответствующих ADR.
· Глоссарий: Glossary.md
