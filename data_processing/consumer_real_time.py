from flask import Flask, render_template
import json
import pandas as pd
from confluent_kafka import Consumer, KafkaError
import threading
from datetime import datetime, timedelta
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask App
app = Flask(__name__, template_folder='../visuelization/templates')

# Global DataFrame to store data
data_df = pd.DataFrame(columns=['Symbol', 'Date', 'Open', 'High', 'Low', 'Close', 'Volume'])

# Maximum number of data points to store per symbol
MAX_DATA_POINTS = 5000


def get_trading_day():
    """Return the current trading day. If weekend or after hours, return the last trading day"""
    now = datetime.now()
    weekday = now.weekday()
    current_hour = now.hour

    # If it's weekend (5=Saturday, 6=Sunday)
    if weekday == 5:  # Saturday
        # Return Friday
        return (now - timedelta(days=1)).strftime('%Y-%m-%d')
    elif weekday == 6:  # Sunday
        # Return Friday
        return (now - timedelta(days=2)).strftime('%Y-%m-%d')

    # If it's before market open (9:30 AM) or after it closed (4:00 PM)
    if current_hour < 9 or (current_hour == 9 and now.minute < 30) or current_hour >= 16:
        # If Monday and before market open, return Friday
        if weekday == 0 and current_hour < 9:
            return (now - timedelta(days=3)).strftime('%Y-%m-%d')
        # Otherwise return previous day
        elif current_hour < 9 or (current_hour == 9 and now.minute < 30):
            return (now - timedelta(days=1)).strftime('%Y-%m-%d')
        # If after market close, return today
        else:
            return now.strftime('%Y-%m-%d')

    # During market hours, return today
    return now.strftime('%Y-%m-%d')


def create_kafka_consumer():
    """Create and return a Kafka consumer instance"""
    conf = {
        'bootstrap.servers': 'localhost:9092',
        'group.id': 'flask_consumer',
        'auto.offset.reset': 'earliest',  # Changed to 'earliest' to get all historical data
        'session.timeout.ms': 6000,
        'max.poll.interval.ms': 6000000
    }
    consumer = Consumer(conf)
    consumer.subscribe(['financial_data'])
    return consumer


def consume_messages():
    """Consume messages from Kafka and update DataFrame"""
    global data_df
    consumer = create_kafka_consumer()

    logger.info("Starting Kafka consumer thread...")
    message_count = 0

    while True:
        try:
            msg = consumer.poll(1.0)
            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    logger.error(f"Kafka error: {msg.error()}")
                    continue

            # Process the message
            try:
                data = json.loads(msg.value().decode('utf-8'))

                # Ensure date is in proper format
                if 'Date' in data:
                    data['Date'] = pd.to_datetime(data['Date'])
                else:
                    data['Date'] = pd.Timestamp.now()

                # Add the record to DataFrame
                new_row = pd.DataFrame([data])
                data_df = pd.concat([data_df, new_row], ignore_index=True)

                # Deduplication
                data_df = data_df.drop_duplicates(subset=['Symbol', 'Date'], keep='last')

                message_count += 1

                # Periodic logging
                if message_count % 100 == 0:
                    logger.info(f"Processed {message_count} messages so far")

                # Limit the number of data points for each symbol
                for symbol in data_df['Symbol'].unique():
                    symbol_data = data_df[data_df['Symbol'] == symbol]
                    if len(symbol_data) > MAX_DATA_POINTS:
                        symbol_indices = symbol_data.index.sort_values()
                        to_drop = symbol_indices[:-MAX_DATA_POINTS]
                        data_df = data_df.drop(to_drop)

            except Exception as e:
                logger.error(f"Error processing message: {e}")

        except Exception as e:
            logger.error(f"Consumer thread error: {e}")
            # Reconnect in case of error
            try:
                consumer.close()
                time.sleep(5)
                consumer = create_kafka_consumer()
                logger.info("Reconnected to Kafka")
            except:
                logger.error("Failed to reconnect to Kafka")
                time.sleep(10)



# Start consumer in a separate thread
threading.Thread(target=consume_messages, daemon=True).start()

@app.route('/')
def index():
    global data_df
    symbols = sorted(data_df['Symbol'].unique())
    return render_template('symbol_chart.html', symbols=symbols)


@app.route('/symbol/<symbol>')
def symbol_page(symbol):
    return render_template('symbol_graph.html', symbol=symbol)


@app.route('/data/<symbol>')
def get_symbol_data(symbol):
    """Return the latest data as JSON for the graph for a specific symbol"""
    global data_df
    traces = []

    trading_day = get_trading_day()

    try:
        symbol_data = data_df[data_df['Symbol'] == symbol]
        if not symbol_data.empty:
            logger.info(f"Date range for {symbol}: {symbol_data['Date'].min()} to {symbol_data['Date'].max()}")
            logger.info(f"Unique dates for {symbol}: {symbol_data['Date'].dt.date.unique()}")

        # Less strict filtering - get data from the current day's date string
        current_date_str = trading_day
        df_symbol = symbol_data[(symbol_data['Date'].dt.strftime('%Y-%m-%d') == current_date_str)].sort_values('Date')

        # If no data found with strict filtering, try getting the most recent data
        if df_symbol.empty:
            logger.warning(f"No data found for {symbol} on exact date {trading_day}, fetching most recent data")
            df_symbol = symbol_data.sort_values('Date', ascending=False).head(100)

        if df_symbol.empty:
            logger.warning(f"No data available for {symbol}")
            return json.dumps([])

        # Log information about the data
        logger.info(f"Returning data for {symbol}: {len(df_symbol)} points")
        logger.info(f"Time range: {df_symbol['Date'].min()} to {df_symbol['Date'].max()}")

        # Convert dates to strings for JSON
        date_strings = df_symbol['Date'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist()

        traces.append({
            'x': date_strings,
            'open': df_symbol['Open'].tolist(),
            'high': df_symbol['High'].tolist(),
            'low': df_symbol['Low'].tolist(),
            'close': df_symbol['Close'].tolist(),
            'volume': df_symbol['Volume'].tolist(),
            'type': 'candlestick',
            'name': symbol
        })
    except Exception as e:
        logger.error(f"Error in get_symbol_data route: {e}")
        import traceback
        logger.error(traceback.format_exc())

    return json.dumps(traces)

@app.route('/debug')
def debug():
    """Endpoint to see what data we have for debugging"""
    global data_df
    data = {}

    try:
        for symbol in data_df['Symbol'].unique():
            df_symbol = data_df[data_df['Symbol'] == symbol]
            if df_symbol.empty:
                continue

            data[symbol] = {
                'count': len(df_symbol),
                'unique_times': len(df_symbol['Date'].unique()),
                'earliest': df_symbol['Date'].min().strftime('%Y-%m-%d %H:%M:%S'),
                'latest': df_symbol['Date'].max().strftime('%Y-%m-%d %H:%M:%S'),
                'time_range_hours': (df_symbol['Date'].max() - df_symbol['Date'].min()).total_seconds() / 3600
            }
    except Exception as e:
        logger.error(f"Error in debug route: {e}")
        return json.dumps({"error": str(e)})

    return json.dumps(data)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)