# DesktopwebsocketTrade
# Real-Time Market Data Application #
A real-time market data application that streams and displays live cryptocurrency and forex prices using WebSockets, FastAPI, and Chart.js.
The project is open for use when you want to create a websocket for simple trading currencies platforms improvement and enhancement.
## Table of Contents ##
- Introduction
- Features
- Architecture
- Technologies Used
- Prerequisites
- Installation
- Running the Application
- Usage
- Troubleshooting
- Contributing
- License

## Introduction ##

This project provides a platform to receive and display real-time market data for various cryptocurrencies and forex pairs. It consists of a FastAPI backend that connects to Binance and Kraken WebSocket APIs to fetch live price data and a frontend that visualizes this data in real-time charts and tables.

## Features ##
- Real-time streaming of cryptocurrency and forex prices.
- WebSocket-based communication between backend and frontend.
- Dynamic selection of symbols to monitor.
- Visualization of live data using interactive charts.
- Display of top 20 symbols with the highest percentage change.
- Calculation and display of percentage changes in prices.
- Error handling and reconnection logic for stable performance.

## Architecture ##
- Backend: FastAPI application that connects to Binance and Kraken WebSocket APIs, processes incoming market data, and broadcasts updates to connected clients via WebSockets.
- Frontend: HTML and JavaScript application that connects to the backend WebSocket server to receive live price updates and displays them using tables and Chart.js for graphical representation.
- Database: MongoDB with Beanie ODM for storing trading pair information.

## Technologies Used
- Python 3.8+
- FastAPI
- WebSockets
- MongoDB
- Beanie (MongoDB ODM)
- Binance and Kraken WebSocket APIs
- HTML/CSS/JavaScript
- Chart.js
- Date Adapters for Chart.js (date-fns)
- uvicorn

## Prerequisites
- Python 3.8 or higher
- MongoDB Instance (local or remote)
- Node.js and npm (if you plan to use additional frontend tooling)
- Internet Connection (to connect to Binance and Kraken WebSocket APIs)

## Installation
### Backend Setup
1. Clone the Repository

bash
```
git clone https://github.com/AlukweJonesTerah/realtime-market-data.git
```
```
cd realtime-market-data
```

2. Create a Virtual Environment

bash
```
python -m venv venv

source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```
3. .env setup send a request to the link below to get .env setup configuration


https://docs.google.com/document/d/1KI3QAwVbPenSIjUf3-CdagkV8rhA5MD1w7SymUf17kE/edit?usp=sharing

3. Install Dependencies

bash
```
pip install -r requirements.txt
```
4. Configure MongoDB Connection

Update the MongoDB connection settings in your main.py or create a .env file with the following content:

env

```
MONGODB_URI="mongodb://localhost:27017"
DATABASE_NAME="your_database_name"
```

### Frontend Setup
No specific installation is required for the frontend. The HTML files can be served using the FastAPI static files configuration or any HTTP server.

## Running the Application
Start the Backend Server

bash
```
uvicorn main:app --reload
```
- The backend server will start on``` http://127.0.0.1:8000```. 

### Serving the Frontend
Place your frontend HTML files (index.html, graph.html) in a directory named static in the project root.

Update your FastAPI application to serve static files:

```
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="static"), name="static")
```
Now, you can access the frontend pages at:
```
http://127.0.0.1:8000/static/index.html
http://127.0.0.1:8000/static/graph.html
```
## Usage
### Monitoring Prices

1. Access the Frontend
```
Open http://127.0.0.1:8000/static/index.html in your web browser.
```

2. Enter Symbols

- In the input field, enter the symbols you want to monitor, separated by commas ```(e.g., BTC, ETH, EUR/USD)```.
- Click the Connect button.

3. View Live Updates

- The table will display the current prices and automatically update with new data.
- The percentage change column shows the change since the last update.
- The top 20 symbols with the highest percentage change are displayed in order.

### Viewing Real-Time Price Graphs ###
1. Access the Graph Page
```
Open http://127.0.0.1:8000/static/graph.html in your web browser.
```
2. Select a Symbol

- Use the dropdown menu to select a symbol from the predefined list.
- The chart will initialize and start displaying real-time price data for the selected symbol.

3. Interact with the Chart

- Hover over the chart to see specific data points.
- The chart updates automatically as new data is received.

## Troubleshooting

### Common Issues and Solutions

#### Graph Not Displaying
- Error: Uncaught Error: This method is not implemented: Check that a complete date adapter is provided.

- Solution: Ensure that the date adapter for Chart.js is included in your HTML:

html
````
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
````
#### Canvas Already in Use
- Error: Canvas is already in use. Chart with ID '0' must be destroyed before the canvas with ID 'priceChart' can be reused.

- Solution: Before creating a new chart instance, destroy the existing one:

javascript section
```
if (chart) {
    chart.destroy();
}
```
#### Timestamps Too Far Apart
- Error: 0 and 1729688607931 are too far apart with stepSize of 1 minute

- Solution: Check that the server's system time is correct. Incorrect system time can cause timestamps to be in the future, leading to this error.

    - On the Server, verify and correct the system time:

bash
```
date  # Check current date and time
sudo date -s "YYYY-MM-DD HH:MM:SS"  # Set correct date and time
```
mapped_symbol is Not Defined

- Error: NameError: name 'mapped_symbol' is not defined
- Solution: Ensure that mapped_symbol is defined before it is used in your backend code. This variable should only be used within the scope where it is assigned.
## Contributing
Contributions are welcome! Please follow these steps:

1. Fork the Repository

2. Create a Feature Branch

bash
```
git checkout -b feature/your-feature-name
```
3. Commit Your Changes

bash
```
git commit -m "Add your message here"
```
4. Push to Your Branch

bash
```
git push origin feature/your-feature-name

```
5. Open a Pull Request

License
This project is opened for contribution.

## Acknowledgments
- Binance WebSocket API
- Kraken WebSocket API
- Chart.js
- FastAPI Community
- Beanie ODM

## Contact
For any questions or support, please open an issue in the repository or contact the maintainer at  jtalukwe@kabarak.ac.ke.
