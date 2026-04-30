#!/bin/bash
echo "=== Adaptive Behaviour Summary (last 500 lines per node) ==="
for container in $(docker ps --filter "name=lab_swarm_demo-node" --format '{{.Names}}'); do
  echo -n "$container: "
  docker logs $container --tail 500 2>&1 | grep "adapted weights" | awk -F'scenario=' '{print $2}' | sort | uniq -c | sort -rn | head -3
done
echo "Total swarm scenarios (last 500 lines per node):"
docker compose -f mvp/lab_swarm_demo/docker-compose.yml logs node --tail 500 2>/dev/null | grep "adapted weights" | awk -F'scenario=' '{print $2}' | sort | uniq -c | sort -rn