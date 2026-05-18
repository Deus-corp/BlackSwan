"""
This module handles routes related to strategy mutations, providing a web page
to visualize mutation history and an API endpoint to retrieve mutation data.
"""
import sqlite3
import json
import os
from pathlib import Path
from typing import Any, Dict, List
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from dashboard.routes.base_template import render_page

router = APIRouter()

# Path to the SQLite database for mutation history.
# It defaults to 'data/nonce/nonce.db' relative to the project root.
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
                        scales: {
                            y: {
                                beginAtZero: false, // Allow Y-axis to adapt if values are not near zero
                                title: {
                                    display: true,
                                    text: 'Parameter Value'
                                }
                            }
                        }
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
    Renders the page displaying the history of strategy mutations and parameters.
    """
    return HTMLResponse(render_page(request, MUTATIONS_CONTENT, "Strategy Evolution"))

@router.get("/api/mutations")
async def get_mutations(limit: int = 100) -> Dict[str, Any]:
    """
    Retrieves a list of mutation history entries from the SQLite database.

    Args:
        limit (int): The maximum number of mutation entries to retrieve, ordered by ID descending.

    Returns:
        Dict[str, Any]: A dictionary containing either the list of mutation data or an error message.
    """
    if not DB_PATH.exists():
        return {"error": f"DB not found at {DB_PATH}", "data": []}
    try:
        # Use a 'with' statement for robust connection management
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row  # This allows accessing columns by name
            cur: sqlite3.Cursor = conn.execute(
                "SELECT * FROM mutation_history ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows: List[Dict[str, Any]] = [dict(row) for row in cur.fetchall()]
        return {"data": rows}
    except Exception as e:
        # Catch specific SQLite errors if desired, but general Exception is okay for API.
        raise HTTPException(status_code=500, detail=f"Database error: {e}")