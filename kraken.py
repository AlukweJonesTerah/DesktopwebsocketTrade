import requests

# API endpoint
url = 'https://api.kraken.com/0/public/AssetPairs'

# Send GET request
response = requests.get(url)
data = response.json()

# Extract trading pairs
asset_pairs = data['result']

# Filter for USD pairs
usd_pairs = []
for pair_code, details in asset_pairs.items():
    if '/USD' in details['wsname']:
        usd_pairs.append(details['wsname'])

# Print USD pairs
for pair in usd_pairs:
    print(pair)


import requests

# API endpoint
url = 'https://api.kraken.com/0/public/AssetPairs'

# Send GET request
response = requests.get(url)
data = response.json()

# Extract trading pairs
asset_pairs = data['result']

# Print the list of trading pairs with readable names
for pair_code, details in asset_pairs.items():
    pair_name = details['wsname']  # WebSocket name, e.g., 'XBT/USD'
    alt_name = details['altname']  # Alternative name, e.g., 'XXBTZUSD'
    print(f"{alt_name}: {pair_name}")
