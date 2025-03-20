import yfinance as yf
from confluent_kafka import Producer
import json
import time
import logging
import pandas as pd
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Kafka Configuration
KAFKA_BROKER = "localhost:9092"
KAFKA_TOPIC = "financial_data"
CSV_FILE_PATH = "nasdaq_symbols.csv"


def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")


def create_kafka_producer():
    try:
        conf = {
            'bootstrap.servers': KAFKA_BROKER,
            'client.id': 'streaming_producer'
        }
        producer = Producer(conf)
        print("Confluent Kafka producer created successfully")
        return producer
    except Exception as e:
        print(f"Error creating Confluent Kafka producer: {e}")
        return None


def get_trading_day():
    now = datetime.now()
    weekday = now.weekday()
    current_hour = now.hour

    if weekday == 5:
        return (now - timedelta(days=1)).strftime('%Y-%m-%d')
    elif weekday == 6:
        return (now - timedelta(days=2)).strftime('%Y-%m-%d')

    if current_hour < 9 or (current_hour == 9 and now.minute < 30) or current_hour >= 16:
        if weekday == 0 and current_hour < 9:
            return (now - timedelta(days=3)).strftime('%Y-%m-%d')
        elif current_hour < 9 or (current_hour == 9 and now.minute < 30):
            return (now - timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            return now.strftime('%Y-%m-%d')

    return now.strftime('%Y-%m-%d')


def fetch_current_trading_day_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        trading_day = get_trading_day()
        print(f"Fetching data for trading day: {trading_day}")
        data = stock.history(period="1d", interval="1m")

        print(f"Fetched {len(data)} data points for {symbol}")

        if data.empty:
            print(f"No data available for {symbol}")
            return None

        stock_data_list = []

        for index, row in data.iterrows():
            for col in row.index:
                if pd.isna(row[col]):
                    row[col] = 0

            stock_data = {
                'Symbol': symbol,
                'Date': index.strftime('%Y-%m-%d %H:%M:%S'),
                'Open': float(row['Open']),
                'High': float(row['High']),
                'Low': float(row['Low']),
                'Close': float(row['Close']),
                'Volume': float(row['Volume'])
            }
            stock_data_list.append(stock_data)

        return stock_data_list
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None


def send_data_to_kafka(producer, topic, data):
    try:
        json_data = json.dumps(data)
        key = str(data['Symbol'])
        print(f"Sending data to Kafka for symbol: {data['Symbol']} at {data['Date']}")

        producer.produce(
            topic=topic,
            key=key.encode('utf-8'),
            value=json_data.encode('utf-8'),
            callback=delivery_report
        )
        producer.poll(0)
        return True
    except Exception as e:
        print(f"Error sending data to Kafka: {e}")
        return False


def read_symbols_from_csv(file_path):
    try:
        df = pd.read_csv(file_path)
        symbols = df['Symbol'].dropna().unique().tolist()
        print(f"Loaded {len(symbols)} symbols from CSV file.")
        return symbols
    except Exception as e:
        print(f"Error reading symbols from CSV: {e}")
        return []


def main():
    producer = create_kafka_producer()
    if not producer:
        return

    symbols = read_symbols_from_csv(CSV_FILE_PATH)

    if not symbols:
        print("No symbols found in the CSV. Exiting.")
        return

    initial_data_sent = False

    try:
        while True:
            if not initial_data_sent:
                print("Sending current trading day data for all symbols...")
                for symbol in symbols:
                    data_list = fetch_current_trading_day_data(symbol)
                    if data_list:
                        for data in data_list:
                            send_data_to_kafka(producer, KAFKA_TOPIC, data)
                            time.sleep(0.01)
                initial_data_sent = True
                print("Initial trading day data loaded successfully")
            else:
                for symbol in symbols:
                    print(f"Fetching latest data for {symbol}...")
                    data = fetch_current_trading_day_data(symbol)
                    if data:
                        latest_data = data[-1]
                        send_data_to_kafka(producer, KAFKA_TOPIC, latest_data)

            print(f"Waiting for next update cycle...")
            time.sleep(60)

    except KeyboardInterrupt:
        print("Producer stopped by user")
    finally:
        if producer:
            producer.flush()
            print("Kafka producer flushed and closed")


if __name__ == "__main__":
    main()

