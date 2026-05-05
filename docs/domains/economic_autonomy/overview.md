# Economic Autonomy

The Economic Autonomy domain governs **capital management, trade execution,
and financial sovereignty**.  It transforms raw market signals into
risk‑adjusted trading decisions and ensures the swarm can sustain itself
economically without external funding.

---

## Key Documents

| Document | Focus |
|---|---|
| [Overview](README.en.md) | Introduction to the economic layer. |
| [ROI Dispatcher](roi_dispatcher.en.md) | Kelly‑criterion‑based capital allocation and position sizing. |
| [MEV & PPO Executors](mev_and_ppo_executors.en.md) | High‑frequency agents for Maximal Extractable Value and reinforcement‑learning executors. |
| [Payment Obfuscation](payment_obfuscation.en.md) | Techniques for hiding financial flows (mixers, ZK‑proofs). |
| [Symbiotic Takeover](symbiotic_takeover.en.md) | Strategy for accumulating governance power over DeFi protocols through useful services. |

---

## Decision Flow

1.  **Market In** – price feeds, order books, on‑chain data.
2.  **ROI Dispatcher** – calculates expected utility and risk.
3.  **Survival Objective** – validates trade against terminal goals.
4.  **Executor** – PPO agent or rule‑based executor places the order.
5.  **Account** – payment obfuscation hides the swarm’s footprint.

This domain is what makes BlackSwan **economically self‑sovereign**.