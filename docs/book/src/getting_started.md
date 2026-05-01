# Getting Started

This guide will help you set up and run the BlackSwan swarm on your local machine.

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git

## Installation

```bash
git clone https://github.com/Deus-corp/BlackSwan.git
cd BlackSwan
pip install -r requirements.txt
```
## Running a Single Node

```bash
python mvp/lab_swarm_demo/node_agent.py
```

## Running a Swarm

```bash
docker compose -f mvp/lab_swarm_demo/docker-compose.async.yml up --build -d
docker compose -f mvp/lab_swarm_demo/docker-compose.async.yml logs -f node
```
## Running Tests

```bash
pytest tests/
```
## Formal Verification

```bash
java -cp tla2tools.jar tlc2.TLC formal/tla/Ouroboros.tla -config formal/tla/Ouroboros.cfg
```

## Next Steps

- Read the [Design Principles](design_principles.en.md)
- Explore the [Architecture](architecture/architecture_overview.en.md)
- Check [Implemented Protocols](implemented/ouroboros.md)