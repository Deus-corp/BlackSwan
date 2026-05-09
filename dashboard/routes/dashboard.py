from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

DASHBOARD_HTML = """<!DOCTYPE html>
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
        .tabs { display: flex; gap: 1rem; margin-bottom: 1rem; }
        .tabs a { color: #f0c000; text-decoration: none; padding: 0.5rem 1rem; border-radius: 8px; background: #16213e; }
        .tabs a.active { background: #e94560; color: white; }
    </style>
</head>
<body>
    <h1>🦢 BlackSwan Swarm Dashboard</h1>
<div class="tabs">
    <a href="/">🏠 Main</a>
    <a href="/logs">📜 Logs</a>
    <a href="/dashboard" class="active">📊 Dashboard</a>
    <a href="/settings">⚙️ Settings</a>
</div>
    <div class="grid">
        <div class="card"><h2>Capital</h2><canvas id="capitalChart"></canvas></div>
        <div class="card"><h2>Fitness</h2><canvas id="fitnessChart"></canvas></div>
        <div class="card"><h2>Diversity & CRDT Size</h2><canvas id="diversityChart"></canvas></div>
        <div class="card"><h2>Niche Distribution</h2><canvas id="nicheChart"></canvas></div>
    </div>
<script>
  let charts = {};
  async function fetchMetrics() {
    const res = await fetch('/api/metrics');
    if (!res.ok) return;
    const data = await res.json();
    const labels = Object.keys(data);

    if (charts.capital) charts.capital.destroy();
    charts.capital = new Chart(document.getElementById('capitalChart'), {
      type: 'bar',
      data: { labels, datasets: [{ label: 'Capital', data: labels.map(l => data[l].capital), backgroundColor: '#e94560' }] },
      options: { plugins: { legend: { display: false } } }
    });
    if (charts.fitness) charts.fitness.destroy();
    charts.fitness = new Chart(document.getElementById('fitnessChart'), {
      type: 'bar',
      data: { labels, datasets: [{ label: 'Fitness', data: labels.map(l => data[l].fitness), backgroundColor: '#0f3460' }] },
      options: { plugins: { legend: { display: false } } }
    });
    if (charts.diversity) charts.diversity.destroy();
    charts.diversity = new Chart(document.getElementById('diversityChart'), {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: 'Diversity', data: labels.map(l => data[l].diversity), backgroundColor: '#16c79a' },
          { label: 'CRDT Size', data: labels.map(l => data[l].crdt_size), backgroundColor: '#fca311' }
        ]
      }
    });
    if (charts.niche) charts.niche.destroy();
    const niches = labels.map(l => data[l].niche);
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
"""

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(DASHBOARD_HTML)