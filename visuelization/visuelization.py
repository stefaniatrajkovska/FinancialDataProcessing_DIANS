import psycopg2
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
from flask import Flask, render_template, request, jsonify
import matplotlib.pyplot as plt
import io
import base64

# PostgreSQL configuration settings
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "financial_data_db"
DB_USER = "postgres"
DB_PASSWORD = "financialdataproject"

# Initialize Flask application
app = Flask(__name__, template_folder='../visuelization/templates')

# Configure matplotlib for dark theme
plt.style.use('dark_background')


def fetch_limited_symbols(limit=100):
    """Function that retrieves a limited number of stock symbols from the database."""
    try:
        # Establish database connection
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )

        # Query to get distinct symbols with a limit
        query = f"SELECT DISTINCT symbol FROM financial_data ORDER BY symbol LIMIT {limit};"
        df = pd.read_sql(query, connection)
        connection.close()

        print(f"Initial {limit} symbols loaded")
        return df['symbol'].tolist()

    except Exception as e:
        print(f"Error fetching limited symbols: {e}")
        return []


def fetch_symbols_batch(offset, limit=100):
    """Function that retrieves a batch of symbols with pagination."""
    try:
        # Establish database connection
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )

        cursor = connection.cursor()

        # Get total count of symbols
        cursor.execute("SELECT COUNT(DISTINCT symbol) as total FROM financial_data;")
        total_count = cursor.fetchone()[0]

        # Query to get distinct symbols with pagination
        cursor.execute("""
            SELECT DISTINCT symbol 
            FROM financial_data 
            ORDER BY symbol 
            OFFSET %s 
            LIMIT %s;
        """, (offset, limit))

        symbols = [row[0] for row in cursor.fetchall()]

        connection.close()

        print(f"Loaded symbols {offset} to {offset + len(symbols)} of {total_count}")
        return symbols, total_count

    except Exception as e:
        print(f"Error fetching symbol batch: {e}")
        # Return empty list and 0 count in case of error
        return [], 0
def fetch_data_from_db(symbol):
    """Function that retrieves data for a given symbol from PostgreSQL."""
    try:
        # Connect to database
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )

        # SQL query to get stock data for the specified symbol
        query = f"""
        SELECT symbol, date, open, high, low, close, volume
        FROM financial_data
        WHERE symbol = '{symbol}';
        """

        # Execute query and load results into DataFrame
        df = pd.read_sql(query, connection)
        connection.close()
        return df

    except Exception as e:
        print(f"Error fetching data: {e}")
        return None


def analyze_symbol(symbol, df):
    """Performs machine learning for a given symbol and generates predictions and additional analyses."""
    if df is None or df.empty:
        raise ValueError("Data for this symbol is empty or invalid.")

    # Data preparation - convert dates and create feature for days since start
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    df['days_since_start'] = (df['date'] - df['date'].min()).dt.days

    # LINEAR REGRESSION MODEL
    # Create feature (X) and target (y) variables
    X = df['days_since_start'].values.reshape(-1, 1)  # Independent variable: days since start
    y = df['close'].values  # Dependent variable: closing price

    # Initialize and train the linear regression model
    model = LinearRegression()
    model.fit(X, y)  # Fit model to training data

    # Generate predictions using the trained model for historical data points
    df['predicted_close'] = model.predict(X)

    # Calculate Mean Squared Error to evaluate model accuracy
    # Lower MSE means better fit between actual and predicted values
    mse = mean_squared_error(y, df['predicted_close'])

    # TECHNICAL INDICATORS
    # Calculate Moving Average (3-day window)
    # This smooths price data to identify trends
    df['moving_average'] = df['close'].rolling(window=3).mean()

    # Calculate Daily Price Change as percentage
    # Shows daily price volatility
    df['daily_change'] = df['close'].pct_change() * 100

    # Calculate Volatility (standard deviation over 3-day window)
    # Higher values indicate greater price fluctuation/risk
    df['volatility'] = df['close'].rolling(window=3).std()

    return df, mse


def plot_stock_data(symbol):
    """Creates multiple visualizations for stock data including predictions and indicators"""
    df = fetch_data_from_db(symbol)
    if df is None or df.empty:
        raise ValueError("No data found for the given symbol.")

    # Add 'days_since_start' column
    df['date'] = pd.to_datetime(df['date'])
    df['days_since_start'] = (df['date'] - df['date'].min()).dt.days

    # Calculate all the metrics we need
    X = df['days_since_start'].values.reshape(-1, 1)
    y = df['close'].values
    model = LinearRegression()
    model.fit(X, y)
    df['predicted_close'] = model.predict(X)
    mse = mean_squared_error(y, df['predicted_close'])
    df['moving_average'] = df['close'].rolling(window=3).mean()
    df['daily_change'] = df['close'].pct_change() * 100
    df['volatility'] = df['close'].rolling(window=3).std()

    # Create a figure with 3 subplots arranged vertically
    fig, axs = plt.subplots(3, 1, figsize=(12, 15), gridspec_kw={'height_ratios': [3, 1, 1]}, facecolor='#111111')

    # First subplot: Price Chart with Linear Regression and Moving Average
    axs[0].plot(df['date'], df['close'], label="Close Price", color='#1E88E5', linewidth=2)
    axs[0].plot(df['date'], df['predicted_close'], label="Linear Regression", color='#FB8C00', linestyle='--')
    axs[0].plot(df['date'], df['moving_average'], label="3-Day Moving Average", color='#4CAF50')
    axs[0].set_title(f"Stock Prices for {symbol}", fontsize=16, color='white')
    axs[0].set_ylabel("Price", fontsize=12, color='white')
    axs[0].legend(loc='upper left')
    axs[0].grid(True, alpha=0.3)
    axs[0].tick_params(colors='white')
    axs[0].set_facecolor('#181818')

    # Second subplot: Daily Change (%)
    axs[1].bar(df['date'], df['daily_change'], color='#F44336', alpha=0.7)
    axs[1].axhline(y=0, color='white', linestyle='-', linewidth=0.5)
    axs[1].set_title("Daily Price Change (%)", fontsize=14, color='white')
    axs[1].set_ylabel("Change %", fontsize=12, color='white')
    axs[1].grid(True, alpha=0.3)
    axs[1].tick_params(colors='white')
    axs[1].set_facecolor('#181818')

    # Third subplot: Volatility
    axs[2].plot(df['date'], df['volatility'], color='#9C27B0', linewidth=2)
    axs[2].fill_between(df['date'], df['volatility'], alpha=0.3, color='#9C27B0')
    axs[2].set_title("Price Volatility (3-Day STD)", fontsize=14, color='white')
    axs[2].set_xlabel("Date", fontsize=12, color='white')
    axs[2].set_ylabel("Volatility", fontsize=12, color='white')
    axs[2].grid(True, alpha=0.3)
    axs[2].tick_params(colors='white')
    axs[2].set_facecolor('#181818')

    # Improve layout
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.3)

    # Convert plot to base64 encoded image for web display
    img = io.BytesIO()
    plt.savefig(img, format='png', dpi=100, facecolor='#111111')
    img.seek(0)
    img_b64 = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close(fig)
    return img_b64, mse


def plot_historical_data(symbol, df):
    """Creates a historical price chart with dark theme"""
    if df is None or df.empty:
        raise ValueError("No data found for the given symbol.")

    # Ensure date is datetime
    df['date'] = pd.to_datetime(df['date'])

    # Create figure with dark background
    fig, ax = plt.subplots(figsize=(10, 5), facecolor='#111111')

    # Plot data with enhanced colors for dark theme
    ax.plot(df["date"], df["open"], label="Open Price", linestyle="dashed", color="#64B5F6")
    ax.plot(df["date"], df["high"], label="High Price", linestyle="solid", color="#4CAF50")
    ax.plot(df["date"], df["low"], label="Low Price", linestyle="solid", color="#F44336")
    ax.plot(df["date"], df["close"], label="Close Price", linestyle="solid", color="#1E88E5")

    # Style the plot for dark theme
    ax.set_xlabel("Date", color="white")
    ax.set_ylabel("Price", color="white")
    ax.set_title(f"Stock Prices for {symbol}", color="white")
    ax.legend()
    ax.tick_params(colors="white")
    ax.set_facecolor('#181818')
    ax.grid(alpha=0.3)

    # Save to base64
    img = io.BytesIO()
    plt.savefig(img, format='png', facecolor='#111111')
    img.seek(0)
    img_b64 = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close(fig)

    return img_b64


# FLASK ROUTES

@app.route('/', methods=['GET'])
def index():
    """Home page route that displays limited number of symbols initially"""
    initial_symbols = fetch_limited_symbols(100)  # Load first 100 symbols
    return render_template('db_symbols.html', symbols=initial_symbols)


@app.route('/api/symbols', methods=['GET'])
def api_symbols():
    """API endpoint to fetch symbols in batches with pagination"""
    try:
        # Get offset and limit parameters from the request
        offset = request.args.get('offset', default=0, type=int)
        limit = request.args.get('limit', default=100, type=int)

        print(f"API request received: offset={offset}, limit={limit}")

        # Fetch the batch of symbols
        symbols, total_count = fetch_symbols_batch(offset, limit)

        # Return as JSON
        response = {
            'symbols': symbols,
            'total_count': total_count,
            'offset': offset,
            'limit': limit
        }
        print(f"Returning {len(symbols)} symbols")
        return jsonify(response)

    except Exception as e:
        error_msg = f"Error in api_symbols: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500


@app.route('/stock/<symbol>', methods=['GET'])
def stock(symbol):
    """Route to display detailed analysis for a specific stock symbol"""
    df = fetch_data_from_db(symbol)

    if df is None or df.empty:
        return render_template('db_symbols_data_graph.html', error="No data found for the given symbol.", symbol=symbol)

    try:
        # Generate visualization and get MSE value
        img_b64, mse = plot_stock_data(symbol)

        # Get additional calculations from analyze_symbol
        df, _ = analyze_symbol(symbol, df)

        # Get latest values of technical indicators for display
        moving_average = df['moving_average'].iloc[-1] if 'moving_average' in df else None
        daily_change = df['daily_change'].iloc[-1] if 'daily_change' in df else None
        volatility = df['volatility'].iloc[-1] if 'volatility' in df else None

        # Render template with all data and visualization
        return render_template('db_symbols_data_graph.html',
                               img_b64=img_b64,
                               symbol=symbol,
                               mse=mse,
                               moving_average=moving_average,
                               daily_change=daily_change,
                               volatility=volatility)

    except ValueError as e:
        return render_template('db_symbols_data_graph.html', error=str(e), symbol=symbol)


@app.route('/historical_data/<symbol>', methods=['GET'])
def historical_data(symbol):
    """Route to display the historical stock price chart for a symbol"""
    df = fetch_data_from_db(symbol)

    if df is None or df.empty:
        return render_template('db_symbols_historical_data.html', error="No data found for the given symbol.", symbol=symbol)

    # Generate dark-themed chart for historical prices
    img_b64 = plot_historical_data(symbol, df)

    return render_template('db_symbols_historical_data.html', img_b64=img_b64, symbol=symbol)


# Run the Flask application in debug mode
if __name__ == '__main__':
    app.run(debug=True)