#!/bin/bash
echo "=== Curiosity Engine Statistics ==="
for container in $(docker ps --filter "name=lab_swarm_demo-node" --format '{{.Names}}'); do
  generated=$(docker logs $container 2>&1 | grep -c "curiosity generated hypothesis")
  echo "$container: generated $generated hypotheses"
done
echo "Total across swarm:"
docker compose -f mvp/lab_swarm_demo/docker-compose.yml logs node 2>/dev/null | grep -c "curiosity generated hypothesis"