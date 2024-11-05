let ws;
let assetChart;
let timeLabels = [];
let assetPrices = [];

// Function to create the chart
function createChart(symbol) {
    const ctx = document.getElementById('assetChart').getContext('2d');

    // Destroy existing chart if it exists
    if (assetChart) {
        assetChart.destroy();
    }

    // Initialize a new Chart instance
    assetChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: timeLabels,
            datasets: [{
                label: `Price of ${symbol}`,
                data: assetPrices,
                borderColor: 'rgba(75, 192, 192, 1)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                fill: false,
                tension: 0.1,
            }]
        },
        options: {
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'second',
                        displayFormats: {
                            second: 'HH:mm:ss'
                        }
                    },
                    title: {
                        display: true,
                        text: 'Time'
                    }
                },
                y: {
                    beginAtZero: false,
                    title: {
                        display: true,
                        text: 'Price (USD)'
                    }
                }
            },
            plugins: {
                tooltip: {
                    mode: 'nearest',
                    intersect: false
                },
                legend: {
                    display: true
                }
            },
            animation: false
        }
    });
}

// Function to add data to the chart
function addData(price, timestamp) {
    if (!assetChart) return; // Ensure assetChart is defined

    const time = new Date(timestamp);
    timeLabels.push(time);
    assetPrices.push(price);

    // Limit the number of data points for better performance
    const maxDataPoints = 50;
    if (timeLabels.length > maxDataPoints) {
        timeLabels.shift();
        assetPrices.shift();
    }

    assetChart.update('none');
}

// Function to establish WebSocket connection and handle data
function connectToAsset() {
    const symbol = document.getElementById('assetSymbol').value.trim().toUpperCase();
    if (ws) ws.close();  // Close previous WebSocket connection if open

    ws = new WebSocket(`ws://127.0.0.1:8000/ws/market/${symbol}`);

    ws.onopen = () => {
        console.log(`WebSocket connected for asset ${symbol}`);

        // Reset time labels and price data
        timeLabels = [];
        assetPrices = [];

        // Create or update the chart for the new asset
        createChart(symbol);
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "update") {
            const { price, timestamp } = data;
            addData(price, timestamp);  // Add new data to the chart
        } else if (data.type === "initial") {
            console.log("Initial data received:", data);
        }
    };

    ws.onclose = () => {
        console.log("WebSocket connection closed");
    };

    ws.onerror = (error) => {
        console.error("WebSocket error:", error);
    };
}
