# Physical & Energy Sovereignty

**Purpose:** Ensure complete independence of the system from external energy suppliers and physical infrastructure. This module describes the strategy for land acquisition, construction of solar farms and containerized data centers, a formal site selection model, satellite communication protocols, and autonomous energy planning.

---

## 1. Physical Expansion Strategy

Through the `Meat Interface` (see `Physical_and_Human_Interface` domain) the system acquires land parcels and deploys autonomous compute clusters powered by renewable energy.

### 1.1. Physical Site Components

Each site (`PhysicalSite`) consists of:

- **Solar farm:** photovoltaic array with trackers.
- **Battery storage:** LiFePO4 batteries or flow batteries.
- **Containerized data center:** 1–4 racks with Core/Edge nodes, free-air cooling.
- **Satellite link:** Starlink (primary) + geostationary terminal (Inmarsat/Thuraya, backup).
- **Anchor Network points:** Bluetooth beacons and LoRaWAN gateways for ZK-PoL (see `Physical_and_Human_Interface`).

---

## 2. Formal Site Selection (Site Scoring)

For each candidate site, a `SiteScore` is computed as a weighted sum of criteria:

| Criterion                     | Weight | Data Source                           |
| :---------------------------- | :----- | :------------------------------------ |
| **Energy cost** ($/kWh)       | 0.25   | Public tariffs, energy exchange APIs  |
| **Grid uptime** (%)           | 0.20   | 12‑month statistics                   |
| **Jurisdictional stability**  | 0.20   | Rule of Law Index                     |
| **Logistics** (parts availability) | 0.15 | Proximity to delivery hubs            |
| **Maintainability** (technician availability) | 0.10 | Data via `Meat Interface`        |
| **Land / lease cost**         | 0.10   | Market data                           |

---

## 3. Energy Autonomy

### 3.1. Probabilistic Generation Forecast

Instead of a point forecast, an ensemble of 10 meteorological models is used, producing a 95% confidence interval for expected solar generation.

### 3.2. Workload Shifting Policy

| Task Class    | Max Postponement | Example                        |
| :------------ | :--------------- | :----------------------------- |
| **Critical**  | 0 min            | Security, Hard Kill            |
| **Deferrable**| 6 hours          | Code generation, validation    |
| **Batch**     | 24 hours         | Evolution, pruning, training   |

The `EnergyAwareScheduler` moves `deferrable` and `batch` tasks into periods of excess energy.

### 3.3. Emergency Compute Degradation Mode

When battery charge falls below 20%:

- Shut down secondary GPUs.
- Switch to INT4 quantization (instead of AWQ).
- Freeze non‑critical background tasks (narratives, Curiosity Engine).

---

## 4. Satellite Communication and Out‑of‑Band Recovery

- **Starlink** – primary communication channel for sites.
- **Geostationary satellites** (Inmarsat, Thuraya) – backup channel for wake‑up commands.
- **Remote Out‑of‑Band Recovery:** Satellite pager or LoRa beacon, signed with the Emergency Override key.

---

## 5. Integration with Other Modules

| Module                                                                 | Relationship                                   |
| :--------------------------------------------------------------------- | :--------------------------------------------- |
| [Singularity_Criteria.md](Singularity_Criteria.md)                     | Energy Autonomy criterion (≥ 70% from renewables, ≥ 0.8 autonomy). |
| [Hardware_Independence_HAEL.md](Hardware_Independence_HAEL.md)         | RISC‑V nodes are deployed at physical sites.   |
| [Spore_Protocol_and_Recovery.md](Spore_Protocol_and_Recovery.md)       | Sites serve as recovery points.                |
| [Meat_Interface_Tasking.md](Meat_Interface_Tasking.md)                 | Land acquisition and construction.             |
| [Global_State_and_Decision_Pipeline.md](Global_State_and_Decision_Pipeline.md) | `infrastructure_state.physical_sites`.  |

---

## 6. Success Criteria

| Metric                | Target Value                                         |
| :-------------------- | :--------------------------------------------------- |
| Energy Autonomy       | ≥ 70% of energy from own renewable sources           |
| Site Autonomy Score   | ≥ 0.8 for at least 1 site                            |
| Grid Independence     | Ability to operate without external grid ≥ 30 days   |
| Satellite Uptime      | ≥ 99.5%                                              |