#!/usr/bin/env python3
"""
BlackSwan Web Dashboard – FastAPI server that shows swarm metrics in the browser.
Usage: python3 web_dashboard.py   (opens http://localhost:8000)
"""
import re
from collections import defaultdict
import docker
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI(title="BlackSwan Swarm Dashboard")
client = docker.from_env()

# ---------- Кэш метрик ----------
metrics_cache = {"capital": {}, "fitness": {}, "diversity": {}, "crdt_size": {}, "niche": {}}
LOG_PATTERN = re.compile(
    r'SwarmNode:\[([^\]]+)\]\s+step=(\d+)\s+capital=([\d.]+)\s+dq=[\d.]+\s+fitness=([\d.]+)\s+diversity=([\d.]+)\s+crdt_size=(\d+)\s+niche=(\w+)'
)

def update_metrics():
    containers = client.containers.list(filters={"name": "lab_swarm_demo-node", "status": "running"})
    for c in containers:
        try:
            log = c.logs(tail=100).decode('utf-8')
        except docker.errors.APIError:
            continue
        matches = LOG_PATTERN.findall(log)
        if matches:
            last = matches[-1]
            node = c.name.replace("lab_swarm_demo-", "")
            metrics_cache["capital"][node] = float(last[2])
            metrics_cache["fitness"][node] = float(last[3])
            metrics_cache["diversity"][node] = float(last[4])
            metrics_cache["crdt_size"][node] = int(last[5])
            metrics_cache["niche"][node] = last[6]

@app.get("/")
def index():
    """Отдаёт HTML-страницу с графиками."""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>BlackSwan Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  body { font-family: sans-serif; background: #1a1a2e; color: #e0e0e0; margin: 20px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  .card { background: #16213e; border-radius: 12px; padding: 15px; }
  canvas { max-height: 300px; }
  h2 { margin-top: 0; }
</style>
</head>
<body>
  <h1>🦢 BlackSwan Swarm Dashboard</h1>
  <div class="grid">
    <div class="card"><h2>Capital</h2><canvas id="capitalChart"></canvas></div>
    <div class="card"><h2>Fitness</h2><canvas id="fitnessChart"></canvas></div>
    <div class="card"><h2>Diversity & CRDT Size</h2><canvas id="diversityChart"></canvas></div>
    <div class="card"><h2>Niche Distribution</h2><canvas id="nicheChart"></canvas></div>
  </div>
<script>
  let charts = {};
  async function fetchMetrics() {
    const res = await fetch('/metrics');
    const data = await res.json();
    const labels = Object.keys(data.capital);

    // Capital
    if (charts.capital) charts.capital.destroy();
    charts.capital = new Chart(document.getElementById('capitalChart'), {
      type: 'bar',
      data: { labels, datasets: [{ label: 'Capital', data: labels.map(l => data.capital[l]), backgroundColor: '#e94560' }] },
      options: { plugins: { legend: { display: false } } }
    });
    // Fitness
    if (charts.fitness) charts.fitness.destroy();
    charts.fitness = new Chart(document.getElementById('fitnessChart'), {
      type: 'bar',
      data: { labels, datasets: [{ label: 'Fitness', data: labels.map(l => data.fitness[l]), backgroundColor: '#0f3460' }] },
      options: { plugins: { legend: { display: false } } }
    });
    // Diversity & CRDT Size (две оси)
    if (charts.diversity) charts.diversity.destroy();
    charts.diversity = new Chart(document.getElementById('diversityChart'), {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: 'Diversity', data: labels.map(l => data.diversity[l]), backgroundColor: '#16c79a' },
          { label: 'CRDT Size', data: labels.map(l => data.crdt_size[l]), backgroundColor: '#fca311' }
        ]
      }
    });
    // Niche pie
    if (charts.niche) charts.niche.destroy();
    const niches = labels.map(l => data.niche[l]);
    const nicheCounts = {};
    niches.forEach(n => nicheCounts[n] = (nicheCounts[n] || 0) + 1);
    charts.niche = new Chart(document.getElementById('nicheChart'), {
      type: 'pie',
      data: {
        labels: Object.keys(nicheCounts),
        datasets: [{ data: Object.values(nicheCounts), backgroundColor: ['#e94560', '#0f3460', '#16c79a'] }]
      }
    });
  }
  fetchMetrics();
  setInterval(fetchMetrics, 5000);
</script>
</body>
</html>
    """)

@app.get("/metrics")
def get_metrics():
    """Эндпоинт с актуальными метриками."""
    update_metrics()
    return metrics_cache

if __name__ == "__main__":
    print("🌐 Запуск веб-дашборда на http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")