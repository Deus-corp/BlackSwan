#!/bin/bash
set -e
export NODE_ID="${HOSTNAME:-unknown}"
export PORT="${GOSSIP_PORT:-9777}"

# Случайная задержка 0–10 секунд, чтобы ноды стартовали вразнобой
sleep $(( RANDOM % 10 ))

TOTAL_NODES=${TOTAL_NODES:-3}
# безопасно извлекаем номер из hostname, например lab_swarm_demo-node-2
MY_INDEX=$(echo "$NODE_ID" | grep -oE '[0-9]+' | tail -1)
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
exec python -u -m mvp.lab_swarm_demo.node_agent