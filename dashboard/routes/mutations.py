"""
This module handles routes related to strategy mutations, providing a web page
to visualize mutation history and an API endpoint to retrieve mutation data.
"""
import sqlite3
import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse

from dashboard.routes.base_template import render_page

router: APIRouter = APIRouter()

# Path to the SQLite database for mutation history.
DB_PATH: Path = Path(os.getenv(
    "NONCE_DB_PATH",
    str(Path(__file__).resolve().parent.parent.parent / "data" / "nonce" / "nonce.db")
))

# HTML content for the mutations page, including a Chart.js canvas and script
MUTATIONS_CONTENT: str = """
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
                if (!data || !data.length) {
                    console.log("No mutation data to display.");
                    return;
                }

                const timestamps = data.map(d => new Date(d.timestamp * 1000).toLocaleTimeString());
                const getParam = (d, key) => { try { return JSON.parse(d.new_params)[key]; } catch { return null; } };

                const maxRisk = data.map(d => getParam(d, 'max_risk_per_trade'));
                const phiLLM = data.map(d => getParam(d, 'phi_llm'));
                const stopLoss = data.map(d => getParam(d, 'stop_loss_ratio'));

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
                        plugins: { legend: { position: 'top' }, title: { display: true, text: 'Strategy Parameters' } }
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
async def mutations_page(request: Request) -> HTMLResponse:
    """
    Renders the page displaying the history of strategy mutations.

    Args:
        request: The incoming FastAPI request.

    Returns:
        An HTML response containing the rendered mutations dashboard.
    """
    return HTMLResponse(render_page(request, MUTATIONS_CONTENT, "Strategy Evolution"))

@router.get("/api/mutations")
async def get_mutations(limit: int = 100) -> Dict[str, Any]:
    """
    Retrieves a list of mutation history entries from the SQLite database.

    Args:
        limit: The maximum number of entries to return. Defaults to 100.

    Returns:
        A dictionary containing a list of database rows or an error message.

    Raises:
        HTTPException: If the database operation fails.
    """
    if not DB_PATH.exists():
        return {"error": f"DB not found at {DB_PATH}", "data": []}
    
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM mutation_history ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows: List[Dict[str, Any]] = [dict(row) for row in cursor.fetchall()]
        return {"data": rows}
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")