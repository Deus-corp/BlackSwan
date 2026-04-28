#!/bin/bash
set -e

export NODE_ID="${HOSTNAME:-unknown}"

echo "Starting BlackSwan node $NODE_ID"
exec python -m mvp.lab_swarm_demo.node_agent