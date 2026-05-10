// trades.js – страница сделок с анимацией

const tbody = document.querySelector('#trades-table tbody');
let interval;

async function fetchTrades() {
    const res = await fetch('/api/trades');
    const data = await res.json();
    tbody.innerHTML = data.map((trade, index) =>
        `<tr class="trade-row-new" style="animation-delay:${index * 0.03}s">
            <td>${trade.node}</td>
            <td><a href="https://sepolia.etherscan.io/tx/${trade.tx_hash}" target="_blank" style="color:#58a6ff">${trade.tx_hash.substring(0,10)}...</a></td>
            <td class="status-${trade.status}">${trade.status}</td>
        </tr>`
    ).join('');
}

function toggleAutoRefresh() {
    if (document.getElementById('autoRefresh').checked) {
        fetchTrades();
        interval = setInterval(fetchTrades, 10000);
    } else if (interval) {
        clearInterval(interval);
    }
}

fetchTrades();

tbody.innerHTML = data.map((trade, index) =>
    `<tr class="trade-row-new" style="animation-delay:${index * 0.03}s">
        <td>${trade.node}</td>
        <td>${trade.side}</td>
        <td>${trade.amount}</td>
        <td>${trade.symbol}</td>
        <td><a href="https://sepolia.etherscan.io/tx/${trade.tx_hash}" target="_blank" style="color:#58a6ff">${trade.tx_hash.substring(0,10)}...</a></td>
        <td class="status-${trade.status}">${trade.status}</td>
    </tr>`
).join('');