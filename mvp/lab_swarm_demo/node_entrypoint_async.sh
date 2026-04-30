#!/bin/bash
set -e
export NODE_ID="${HOSTNAME:-unknown}"
export PORT="${GOSSIP_PORT:-9777}"

# Генерация списка пиров
# В сети Docker compose имена контейнеров будут lab_swarm_demo-node-1, lab_swarm_demo-node-2 и т.д.
TOTAL_NODES=${TOTAL_NODES:-4}
MY_INDEX=$(echo "$NODE_ID" | grep -o 'node-[0-9]*$' | grep -o '[0-9]*')
if [ -z "$MY_INDEX" ]; then
  MY_INDEX=1
fi

PEERS=""
for i in $(seq 1 $TOTAL_NODES); do
  if [ "$i" != "$MY_INDEX" ]; then
    if [ -n "$PEERS" ]; then
      PEERS="$PEERS,"
    fi
    PEERS="${PEERS}http://lab_swarm_demo-node-${i}:${PORT}"
  fi
done

export PEERS="$PEERS"
echo "Starting async node $NODE_ID on port $PORT with peers: $PEERS"
exec python -m mvp.lab_swarm_demo.node_agent