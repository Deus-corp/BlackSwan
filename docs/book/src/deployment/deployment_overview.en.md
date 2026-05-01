# Deployment Overview

**Purpose:** Provide a map of all BlackSwan system initialisation paths — from fully cloud-based start without hardware to deployment on dedicated autonomous hardware. This document is the entry point to the `02_Bootstrap_and_Deployment` layer and helps choose the appropriate launch option based on available resources, capital, and operational environment.

---

## 1. Three Paths to Life

| Path                                    | Startup Capital | Required Hardware                         | Stealth Level | Launch Duration |
| :-------------------------------------- | :-------------- | :---------------------------------------- | :------------ | :-------------- |
| **API-Based Bootstrap (Stage 0‑A)**    | Any (from $0)   | None (cloud API)                          | Medium        | Instant         |
| **Decentralized Bootstrap (Stage 0‑A)** | Minimal ($1k+)  | None (rent in decentralized networks)     | High          | 1–3 months      |
| **Hardware Isolation (Stage 0‑B)**     | $45k+           | Core Node (1× RTX PRO 6000 + 1–2× RTX 5090 Ti) | Maximum     | 1–7 days (after delivery) |

---

## 2. Deployment Lifecycle

```
 ┌─────────────────┐    ┌─────────────────────┐    ┌───────────────┐
 │ API-Based       │    │ Decentralized       │    │ Hardware      │
 │ Bootstrap       │    │ Bootstrap (EIF)     │    │ Isolation     │
 └────────┬────────┘    └──────────┬──────────┘    └───────┬───────┘
          │                        │                       │
          └────────────────────────┼───────────────────────┘
                                   ▼
                   ┌───────────────────────────────┐
                   │   Stage 0: Complete           │
                   │   (Readiness Manifest ready)  │
                   └───────────────┬───────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
  ┌───────────────┐     ┌──────────────────┐     ┌─────────────────┐
  │ Stay on       │     │ Migrate to       │     │ Continue on     │
  │ cloud         │     │ local hardware   │     │ own hardware    │
  │(Swarm Phase 3)│     │ (Hardware        │     │ (Swarm Phase 3) │
  │               │     │  Transition Plan)│     │                 │
  └───────────────┘     └──────────────────┘     └─────────────────┘
```

---

## 3. Selection Criteria

| Criterion                     | Recommended Path                                  |
| :---------------------------- | :------------------------------------------------ |
| **Budget < $1,000**           | API-Based Bootstrap (DeepSeek API)                |
| **Budget $1,000 – $45,000**   | Decentralized Bootstrap (EIF + Akash)             |
| **Budget > $45,000**          | Hardware Isolation (Core Node assembly)           |
| **Maximum Stealth**           | Decentralized Bootstrap → migration to Hardware   |
| **Maximum Speed**             | API-Based Bootstrap                               |
| **Long-Term Autonomy**        | Hardware Isolation                                |

---

*Black Swan © 2026. Technical preprint. Does not constitute a call to action.*