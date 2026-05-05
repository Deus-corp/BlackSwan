# Getting Started

This guide will help you launch your first BlackSwan swarm in under 5 minutes.

## Prerequisites
- Docker Desktop installed and running.
- Python 3.11+ with `pip` available.
- Git (to clone the repository).

## 1. Clone the repository
```bash
git clone https://github.com/Deus-corp/BlackSwan.git
cd BlackSwan
```

## 2. Launch the Control Panel
The easiest way to manage the swarm is the interactive CLI:

```bash
python3 swarm_control.py
```

From the menu you can:
- Start / stop / rebuild the swarm.
- Change the LLM model.
- Switch between simulated and live (Binance Testnet) market.
- Set your Binance API keys securely.
- Save and view real-time logs.

## 3. Visual monitoring

Start the web dashboard to see capital, fitness, diversity, and niche distribution in your browser:

```bash
python3 web_dashboard.py
```
Open http://localhost:8000.

## 4. Configuration

All settings are in mvp/lab_swarm_demo/docker-compose.async.yml.
Configuration Guide explains every environment variable.

## 5. Next Steps

- Read the [Architecture Overview](architecture/architecture_overview.en.md) to understand the layers and formal contracts.
- Run the [Multi-Model Benchmark](reports/benchmark_10_models_2026-05-03.md) to compare local LLMs.
- Explore the [Spore Protocol](singularity/spore_protocol_and_recovery.en.md) for resilience testing.
- Check the [Roadmap](../roadmap/) for upcoming features.