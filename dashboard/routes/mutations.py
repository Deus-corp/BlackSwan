import sqlite3, json, os
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from dashboard.routes.base_template import render_page

router = APIRouter()

# Путь к базе (теперь data/nonce)
DB_PATH = Path(os.getenv("NONCE_DB_PATH", str(Path(__file__).resolve().parent.parent.parent / "data" / "nonce" / "nonce.db")))

MUTATIONS_CONTENT = """
    <div style="padding: 1rem;">
        <canvas id="mutationsChart" width="800" height="400"></canvas>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        async function loadMutations() {
            try {
                const response = await fetch('/api/mutations?limit=100');
                const json = await response.json();
                if (json.error) {
                    console.error(json.error);
                    return;
                }
                const data = json.data;
                if (!data || !data.length) return;

                const timestamps = data.map(d => new Date(d.timestamp * 1000).toLocaleTimeString());
                const maxRisk = data.map(d => { try { return JSON.parse(d.new_params).max_risk_per_trade; } catch(e) { return null; } });
                const phiLLM = data.map(d => { try { return JSON.parse(d.new_params).phi_llm; } catch(e) { return null; } });
                const stopLoss = data.map(d => { try { return JSON.parse(d.new_params).stop_loss_ratio; } catch(e) { return null; } });

                const ctx = document.getElementById('mutationsChart').getContext('2d');
                if (window.mutationsChart instanceof Chart) {
                    window.mutationsChart.destroy();
                }
                window.mutationsChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: timestamps,
                        datasets: [
                            { label: 'Max Risk', data: maxRisk, borderColor: 'rgb(255, 99, 132)', tension: 0.1 },
                            { label: 'Phi LLM', data: phiLLM, borderColor: 'rgb(54, 162, 235)', tension: 0.1 },
                            { label: 'Stop Loss', data: stopLoss, borderColor: 'rgb(75, 192, 192)', tension: 0.1 }
                        ]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'top' },
                            title: { display: true, text: 'Strategy Parameters Over Time' }
                        },
                        scales: { y: { beginAtZero: true } }
                    }
                });
            } catch (error) {
                console.error('Error loading mutations:', error);
            }
        }
        loadMutations();
        setInterval(loadMutations, 30000);
    </script>
"""

@router.get("/mutations", response_class=HTMLResponse)
async def mutations_page(request: Request):
    return HTMLResponse(render_page(request, MUTATIONS_CONTENT, "Strategy Evolution"))

@router.get("/api/mutations")
async def get_mutations(limit: int = 100):
    if not DB_PATH.exists():
        return {"error": f"DB not found at {DB_PATH}", "data": []}
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM mutation_history ORDER BY id DESC LIMIT ?", (limit,))
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
        return {"data": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))