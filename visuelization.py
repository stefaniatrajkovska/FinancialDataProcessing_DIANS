#
import keras.src.ops
import psycopg2
import pandas as pd
from sqlalchemy import create_engine
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
from flask import Flask, render_template
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
app = Flask(__name__)


def fetch_all_symbols():
    """Function that retrieves all unique stock symbols from the database."""
    try:
        # Establish database connection
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )

        # Query to get distinct symbols
        query = "SELECT DISTINCT symbol FROM financial_data;"
        df = pd.read_sql(query, connection)
        connection.close()

        print("Symbols found in database:", df['symbol'].tolist())
        return df['symbol'].tolist()

    except Exception as e:
        print(f"Error fetching symbols: {e}")
        return []


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


def analyze_all_symbols(symbols):
    """Analysis of all symbols using machine learning"""
    analysis_results = {}
    for symbol in symbols:
        df = fetch_data_from_db(symbol)
        if df is not None and not df.empty:
            try:
                analyzed_data, mse = analyze_symbol(symbol, df)
                analysis_results[symbol] = {'data': analyzed_data, 'mse': mse}
            except ValueError as e:
                analysis_results[symbol] = {'error': str(e)}
        else:
            analysis_results[symbol] = {'error': "No data for this symbol."}
    return analysis_results


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
    fig, axs = plt.subplots(3, 1, figsize=(12, 15), gridspec_kw={'height_ratios': [3, 1, 1]})

    # First subplot: Price Chart with Linear Regression and Moving Average
    axs[0].plot(df['date'], df['close'], label="Close Price", color='blue', linewidth=2)
    axs[0].plot(df['date'], df['predicted_close'], label="Linear Regression", color='orange', linestyle='--')
    axs[0].plot(df['date'], df['moving_average'], label="3-Day Moving Average", color='green')
    axs[0].set_title(f"Stock Prices for {symbol}", fontsize=16)
    axs[0].set_ylabel("Price", fontsize=12)
    axs[0].legend(loc='upper left')
    axs[0].grid(True, alpha=0.3)

    # Second subplot: Daily Change (%)
    axs[1].bar(df['date'], df['daily_change'], color='red', alpha=0.7)
    axs[1].axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    axs[1].set_title("Daily Price Change (%)", fontsize=14)
    axs[1].set_ylabel("Change %", fontsize=12)
    axs[1].grid(True, alpha=0.3)

    # Third subplot: Volatility
    axs[2].plot(df['date'], df['volatility'], color='purple', linewidth=2)
    axs[2].fill_between(df['date'], df['volatility'], alpha=0.3, color='purple')
    axs[2].set_title("Price Volatility (3-Day STD)", fontsize=14)
    axs[2].set_xlabel("Date", fontsize=12)
    axs[2].set_ylabel("Volatility", fontsize=12)
    axs[2].grid(True, alpha=0.3)

    # Improve layout
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.3)

    # Convert plot to base64 encoded image for web display
    img = io.BytesIO()
    plt.savefig(img, format='png', dpi=100)
    img.seek(0)
    img_b64 = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close(fig)
    return img_b64, mse


# def plot_stock_data(symbol):
#     """Creates visualizations for stock data including predictions and indicators"""
#     df = fetch_data_from_db(symbol)
#     if df is None or df.empty:
#         raise ValueError("No data found for the given symbol.")
#
#     # Add 'days_since_start' column
#     df['date'] = pd.to_datetime(df['date'])
#     df['days_since_start'] = (df['date'] - df['date'].min()).dt.days
#
#     # Generate price chart
#     fig = plt.figure(figsize=(10, 6))
#     plt.plot(df['date'], df['close'], label="Close Price", color='blue')
#
#     # LINEAR REGRESSION VISUALIZATION
#     # Train model and plot the regression line
#     X = df['days_since_start'].values.reshape(-1, 1)
#     y = df['close'].values
#     model = LinearRegression()
#     model.fit(X, y)
#     df['predicted_close'] = model.predict(X)
#     mse = mean_squared_error(y, df['predicted_close'])
#
#     # Plot regression line (trend line) on chart
#     plt.plot(df['date'], df['predicted_close'], label="Linear Regression", color='orange', linestyle='--')
#
#     # Calculate and plot 3-day moving average
#     df['moving_average'] = df['close'].rolling(window=3).mean()
#     plt.plot(df['date'], df['moving_average'], label="3-Day Moving Average", color='green')
#
#     # Calculate and plot daily percent changes
#     df['daily_change'] = df['close'].pct_change() * 100
#     plt.plot(df['date'], df['daily_change'], label="Daily Change", color='red')
#
#     # Calculate and plot 3-day volatility (standard deviation)
#     df['volatility'] = df['close'].rolling(window=3).std()
#     plt.plot(df['date'], df['volatility'], label="Volatility", color='purple')
#
#     # Add chart labels and legend
#     plt.legend()
#     plt.title(f"Stock Prices for {symbol}")
#     plt.xlabel("Date")
#     plt.ylabel("Price")
#
#     # Convert plot to base64 encoded image for web display
#     img = io.BytesIO()
#     plt.savefig(img, format='png')
#     img.seek(0)
#     img_b64 = base64.b64encode(img.getvalue()).decode('utf8')
#     plt.close(fig)
#     return img_b64, mse


# FLASK ROUTES

@app.route('/', methods=['GET'])
def index():
    """Home page route that displays all available symbols"""
    symbols = fetch_all_symbols()
    return render_template('index.html', symbols=symbols)


@app.route('/stock/<symbol>', methods=['GET'])
def stock(symbol):
    """Route to display detailed analysis for a specific stock symbol"""
    df = fetch_data_from_db(symbol)

    if df is None or df.empty:
        return render_template('stock.html', error="No data found for the given symbol.", symbol=symbol)

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
        return render_template('stock.html',
                               img_b64=img_b64,
                               symbol=symbol,
                               mse=mse,
                               moving_average=moving_average,
                               daily_change=daily_change,
                               volatility=volatility)

    except ValueError as e:
        return render_template('stock.html', error=str(e), symbol=symbol)


@app.route('/historical_data/<symbol>', methods=['GET'])
def historical_data(symbol):
    """Route to display the historical stock price chart for a symbol"""
    df = fetch_data_from_db(symbol)

    if df is None or df.empty:
        return render_template('historical_data.html', error="No data found for the given symbol.", symbol=symbol)

    # Generate chart for historical prices
    fig, ax = plt.subplots(figsize=(10, 5))  # Помал график

    # Цртање на Open, High, Low, Close цени
    ax.plot(df["date"], df["open"], label="Open Price", linestyle="dashed")
    ax.plot(df["date"], df["high"], label="High Price", linestyle="solid", color="green")
    ax.plot(df["date"], df["low"], label="Low Price", linestyle="solid", color="red")
    ax.plot(df["date"], df["close"], label="Close Price", linestyle="solid", color="blue")

    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.set_title(f"Stock Prices for {symbol}")
    ax.legend()
    ax.set_xticklabels(df["date"], rotation=45)
    ax.grid()

    # Спремање на графиката во меморијата како слика base64
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    img_b64 = base64.b64encode(img.getvalue()).decode('utf8')

    return render_template('historical_data.html', img_b64=img_b64, symbol=symbol)


# Run the Flask application in debug mode
if __name__ == '__main__':
    app.run(debug=True)



