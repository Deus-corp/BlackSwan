#!/usr/bin/env python3
"""Собирает сводку метрик и сохраняет в logs/daily_report_YYYYMMDD.json"""
import json, os, re, time
from collections import defaultdict
from pathlib import Path
import docker

PREFIX = "lab_swarm_demo-node"
LOG_PATTERN = re.compile(
    r'SwarmNode:\[([^\]]+)\]\s+step=(\d+)\s+capital=([\d.]+)\s+dq=[\d.]+\s+fitness=([\d.]+)\s+diversity=([\d.]+)\s+crdt_size=(\d+)\s+niche=(\w+)'
)
client = docker.from_env()

def collect():
    report = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "nodes": {}}
    for c in client.containers.list(filters={"name": PREFIX, "status": "running"}):
        try:
            log = c.logs(tail=200).decode()
        except:
            continue
        m = LOG_PATTERN.findall(log)
        if m:
            last = m[-1]
            report["nodes"][c.name] = {
                "step": int(last[1]),
                "capital": float(last[2]),
                "fitness": float(last[3]),
                "diversity": float(last[4]),
                "crdt_size": int(last[5]),
                "niche": last[6],
            }
    return report

if __name__ == "__main__":
    dest = Path("logs") / f"daily_report_{time.strftime('%Y%m%d')}.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(collect(), indent=2))
    print(f"Report saved to {dest}")