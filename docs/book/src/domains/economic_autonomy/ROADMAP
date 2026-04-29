# BlackSwan Roadmap

## Current Status: TRL-4 (Component Validation in Laboratory Environment)

### Achievements
- ✅ Formal verification: TLA+ models for NodeLifecycle, D2BFT, GlobalState (LWW registers, invariants), SporeProtocol (extinction prevention). All parse and invariants hold under bounded check.
- ✅ Economic simulator: multi-agent sweep with 6 agents, 200 steps, identified stability zone (burn_rate=0.1, failure_prob=0.0) where Kelly outperforms Random.
- ✅ Docker lab swarm: 8 nodes communicating via Redis pub/sub, processing market ticks, demonstrating positive capital trajectory and auto‑recovery after kill.
- ✅ CI/CD: GitHub Actions run Python tests and formal verification on push/PR.

### TRL-4 Acceptance Criteria (all met)
- Integration of ≥6 key components in a single lab system.
- Multi‑node swarm (8+ nodes) running >1 hour continuously.
- Closed economic cycle with variation (burn rate, random failures simulated).
- Formal models extended for critical properties.
- Auto‑recovery mechanism demonstrated (restart policy + healthcheck).
- Baseline metrics: Kelly advantage ~1500 over Random in stable zone.
- CI passes on every commit.

### Next Milestone: TRL-5 (System Validation in Relevant Environment)
- Deploy to geo‑distributed cheap VPS (Hetzner, Oracle Cloud).
- Implement real CRDT‑based state sync.
- Add real external revenue source (micro‑MEV, API service).
- 72‑hour continuous operation under network latency and random kills.
- Publish technical report / preprint.

### Key Risks and Mitigations
- **Cost**: even small cloud swarm burns money. Start with free tiers.
- **Ethics**: strict separation of hypothetical survival protocols vs implemented code.
- **Value drift**: formal terminal goals invariants to be maintained in all future specs.