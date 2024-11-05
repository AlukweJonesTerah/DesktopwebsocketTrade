import requests

# API endpoint
url = 'https://api.binance.com/api/v3/exchangeInfo'

# Send GET request
response = requests.get(url)
data = response.json()

# Extract trading pairs
symbols = data['symbols']
trading_pairs = [symbol['symbol'] for symbol in symbols]

# Print the list of trading pairs
for pair in trading_pairs:
    print(pair)
