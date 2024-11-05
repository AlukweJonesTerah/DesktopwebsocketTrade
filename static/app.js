const assetTableBody = document.querySelector('#asset-table tbody');

// Store the last known prices and timestamps to calculate changes
let lastPrices = {};
let latestTimestamps = {};

// Function to create a new row for an asset
function createAssetRow(symbol) {
    const row = document.createElement('tr');
    row.setAttribute('id', `asset-${symbol}`);

    const rankCell = document.createElement('td');
    rankCell.setAttribute('class', 'rank');
    rankCell.textContent = '-'; // Placeholder until rank is calculated
    row.appendChild(rankCell);

    const symbolCell = document.createElement('td');
    symbolCell.textContent = symbol;
    row.appendChild(symbolCell);

    const priceCell = document.createElement('td');
    priceCell.setAttribute('class', 'price');
    priceCell.textContent = 'Loading...';
    row.appendChild(priceCell);

    const changeCell = document.createElement('td');
    changeCell.setAttribute('class', 'change');
    changeCell.textContent = '-';
    row.appendChild(changeCell);

    const percentChangeCell = document.createElement('td');
    percentChangeCell.setAttribute('class', 'percent-change');
    percentChangeCell.textContent = '-';
    row.appendChild(percentChangeCell);

    const timestampCell = document.createElement('td');
    timestampCell.setAttribute('class', 'timestamp');
    timestampCell.textContent = '-';
    row.appendChild(timestampCell);

    assetTableBody.appendChild(row);
}

// Function to calculate ranks based on prices
function calculateRanks(prices) {
    // Convert the prices object to an array of [symbol, price] pairs
    const priceArray = Object.entries(prices);

    // Sort the array in descending order of price
    priceArray.sort((a, b) => b[1] - a[1]);

    // Assign ranks
    const ranks = {};
    priceArray.forEach(([symbol, price], index) => {
        ranks[symbol] = index + 1; // Rank starts from 1
    });

    return ranks;
}

// Function to update an existing row with new data
function updateAssetRow(symbol, price, timestamp) {
    const row = document.querySelector(`#asset-${symbol}`);
    if (row) {
        const priceCell = row.querySelector('.price');
        const changeCell = row.querySelector('.change');
        const percentChangeCell = row.querySelector('.percent-change');
        const timestampCell = row.querySelector('.timestamp');

        const lastPrice = lastPrices[symbol] || price;
        const priceChange = price - lastPrice;
        const percentChange = ((priceChange) / lastPrice) * 100;

        // Update cells
        priceCell.textContent = price.toFixed(4);
        changeCell.textContent = priceChange >= 0 ? `+${priceChange.toFixed(4)}` : priceChange.toFixed(4);
        percentChangeCell.textContent = priceChange >= 0 ? `+${percentChange.toFixed(2)}%` : `${percentChange.toFixed(2)}%`;
        timestampCell.textContent = new Date(timestamp).toLocaleTimeString();

        // Apply color classes based on change
        if (priceChange > 0) {
            changeCell.classList.add('positive-change');
            changeCell.classList.remove('negative-change');
            percentChangeCell.classList.add('positive-change');
            percentChangeCell.classList.remove('negative-change');
        } else if (priceChange < 0) {
            changeCell.classList.add('negative-change');
            changeCell.classList.remove('positive-change');
            percentChangeCell.classList.add('negative-change');
            percentChangeCell.classList.remove('positive-change');
        } else {
            // No change
            changeCell.classList.remove('positive-change', 'negative-change');
            percentChangeCell.classList.remove('positive-change', 'negative-change');
        }

        // Update the last known price and timestamp
        lastPrices[symbol] = price;
        latestTimestamps[symbol] = timestamp;
    }
}

// WebSocket connection
const socket = new WebSocket('ws://127.0.0.1:8000/ws/market/ALL');

// Handle incoming messages
socket.onmessage = function(event) {
    const data = JSON.parse(event.data);

    if (data.type === 'initial') {
        // Initial data containing all assets
        const prices = data.data;
        const timestamps = data.timestamps || {};
        const ranks = calculateRanks(prices);

        for (const symbol in prices) {
            createAssetRow(symbol);
            lastPrices[symbol] = prices[symbol];
            latestTimestamps[symbol] = timestamps[symbol] || Date.now();
            updateAssetRow(symbol, prices[symbol], latestTimestamps[symbol]);

            // Update rank
            const row = document.querySelector(`#asset-${symbol}`);
            const rankCell = row.querySelector('.rank');
            rankCell.textContent = ranks[symbol];
        }
    } else if (data.type === 'update') {
        // Update for a specific asset
        const symbol = data.symbol;
        const price = data.price;
        const timestamp = data.timestamp;

        if (!lastPrices.hasOwnProperty(symbol)) {
            // New asset, create a row
            createAssetRow(symbol);
            lastPrices[symbol] = price; // Initialize last price
        }

        updateAssetRow(symbol, price, timestamp);

        // Update last known price and timestamp
        lastPrices[symbol] = price;
        latestTimestamps[symbol] = timestamp;

        // Recalculate and update ranks
        const ranks = calculateRanks(lastPrices);
        for (const sym in lastPrices) {
            const row = document.querySelector(`#asset-${sym}`);
            const rankCell = row.querySelector('.rank');
            rankCell.textContent = ranks[sym];
        }
    }
};

// Handle WebSocket connection open event
socket.onopen = function() {
    console.log('WebSocket connection established.');
};

// Handle WebSocket error event
socket.onerror = function(error) {
    console.error('WebSocket error:', error);
};

// Handle WebSocket close event
socket.onclose = function(event) {
    console.log('WebSocket connection closed:', event);
};
