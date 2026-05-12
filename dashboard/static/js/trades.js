// trades.js – загрузка и отображение списка трейдов с анимацией
let autoRefreshInterval = null;

async function fetchTrades() {
    const tbody = document.querySelector('#trades-table tbody');
    if (!tbody) return;
    try {
        const res = await fetch('/api/trades');
        const data = await res.json();
        if (!data.length) {
            tbody.innerHTML = '<tr><td colspan="6">No trades found.</td></tr>';
            return;
        }
        tbody.innerHTML = data.map((t, idx) => {
            const txHash = t.tx_hash || 'N/A';
            const truncated = txHash.substring(0, 10) + '...';
            const link = txHash !== 'N/A' ? `<a href="https://sepolia.etherscan.io/tx/${txHash}" target="_blank">${truncated}</a>` : truncated;
            const amount = t.amount || '—';
            return `<tr class="trade-row-new" style="animation-delay:${idx * 0.03}s">
                <td>${t.node || 'unknown'}</td>
                <td>${t.side || 'unknown'}</td>
                <td>${amount}</td>
                <td>${t.symbol || 'WETH/USDC'}</td>
                <td>${link}</td>
                <td class="status-${t.status}">${t.status || 'unknown'}</td>
            </tr>`;
        }).join('');
    } catch (e) {
        console.error('Error fetching trades:', e);
    }
}

function toggleAutoRefresh() {
    const checkbox = document.getElementById('autoRefresh');
    if (checkbox && checkbox.checked) {
        autoRefreshInterval = setInterval(fetchTrades, 10000);
    } else if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

// Первая загрузка
fetchTrades();