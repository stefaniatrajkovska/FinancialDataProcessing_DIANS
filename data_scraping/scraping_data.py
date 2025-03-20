import yfinance as yf
import pandas as pd

# Reading symbols from the file
with open("nasdaq_symbols.csv", "r") as file:
    symbols = [line.strip() for line in file.readlines() if line.strip() and line.strip() != "Symbol"]

# List for storing data
all_data = []

# Fetching data for each symbol
for symbol in symbols:
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="5d")  # Fetching the last 5 days of data

        # Adding the "Symbol" column
        hist.insert(0, "Symbol", symbol)

        # Keeping only the required columns
        hist = hist.reset_index()[["Date", "Symbol", "Open", "High", "Low", "Close", "Volume"]]

        # Adding to the list
        all_data.append(hist)

    except Exception as e:
        print(f"Error for {symbol}: {e}")

# Merging all data into one DataFrame
df = pd.concat(all_data, ignore_index=True)

# Saving to CSV in the correct format
df.to_csv("stock_data.csv", index=False)

print("File saved as stock_data.csv with the correct format.")
