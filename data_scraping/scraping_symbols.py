import requests
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Function to fetch all NASDAQ symbols via API
def fetch_nasdaq_symbols():
    url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=25&offset=0&download=true"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json",
    }

    try:
        print(f"Sending request to {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Check if the request was successful

        # Parse the JSON response
        data = response.json()
        symbols = [row["symbol"] for row in data["data"]["rows"]]

        print(f"Successfully received {len(symbols)} symbols.")
        return symbols

    except requests.exceptions.RequestException as e:
        print(f"Error sending request: {e}")
    except Exception as e:
        print(f"Error parsing data: {e}")
    return []

# Function to save the symbols to a CSV file
def save_symbols_to_csv(symbols, filename="nasdaq_symbols.csv"):
    try:
        df = pd.DataFrame(symbols, columns=["Symbol"])
        df.to_csv(filename, index=False)
        print(f"Symbols saved to {filename}")
    except Exception as e:
        print(f"Error saving symbols to CSV: {e}")

# Main function
def main():
    print("Starting to fetch NASDAQ symbols via API...")
    symbols = fetch_nasdaq_symbols()
    if symbols:
        save_symbols_to_csv(symbols)
    else:
        print("No symbols found.")

if __name__ == "__main__":
    main()
