from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType, DoubleType
import os
import psycopg2
import logging

# Kafka and PostgreSQL configuration
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'historical_financial_data')

DB_HOST = os.getenv('DB_HOST', 'postgres')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'financial_data_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'financialdataproject')

# Connect to PostgreSQL DB
def connect_to_db():
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        logging.info("Successfully connected to PostgreSQL database.")
        return connection
    except Exception as e:
        logging.error(f"Error connecting to PostgreSQL database: {e}")
        return None

def insert_data_into_db(data, connection):
    if connection:
        try:
            cursor = connection.cursor()
            insert_query = """
                INSERT INTO financial_data (symbol, date, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                data['Symbol'],
                data['Date'],
                data['Open'],
                data['High'],
                data['Low'],
                data['Close'],
                data['Volume']
            ))
            connection.commit()
            cursor.close()
            logging.info(f"Data for symbol {data['Symbol']} and date {data['Date']} successfully inserted into the database.")
        except Exception as e:
            logging.error(f"Error inserting data into the database: {e}")

# Define Spark Session
spark = SparkSession.builder \
    .appName("StockDataProcessing") \
    .master("spark://spark-master:7077") \
    .config("spark.sql.shuffle.partitions", "10") \
    .config("spark.jars.packages", "org.postgresql:postgresql:42.7.2,org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0") \
    .config("spark.driver.host", "0.0.0.0") \
    .config("spark.driver.bindAddress", "0.0.0.0") \
    .getOrCreate()

# Define schema for Kafka data
schema = StructType([
    StructField("Symbol", StringType(), True),
    StructField("Date", StringType(), True),
    StructField("Open", DoubleType(), True),
    StructField("High", DoubleType(), True),
    StructField("Low", DoubleType(), True),
    StructField("Close", DoubleType(), True),
    StructField("Volume", DoubleType(), True)
])

# Read Kafka data stream
raw_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC) \
    .option("startingOffsets", "earliest") \
    .load()

df = raw_stream.selectExpr("CAST(key AS STRING) as symbol_key", "CAST(value AS STRING) as json_data")
parsed_df = df.select(
    col("symbol_key"),
    from_json(col("json_data"), schema).alias("data")
).select("symbol_key", "data.*")

# Filter out invalid data
parsed_df = parsed_df.filter(
    col("Symbol").isNotNull() &
    col("Date").isNotNull() &
    col("Open").isNotNull() &
    col("High").isNotNull() &
    col("Low").isNotNull() &
    col("Close").isNotNull() &
    col("Volume").isNotNull()
)

# Write data to PostgreSQL efficiently
def write_to_postgresql(batch_df, batch_id):
    # Connect to PostgreSQL DB once for the batch
    connection = connect_to_db()
    if connection:
        try:
            # Use DataFrame-based bulk insert approach for better performance
            for row in batch_df.collect():
                data = {
                    'Symbol': row['Symbol'],
                    'Date': row['Date'],
                    'Open': row['Open'],
                    'High': row['High'],
                    'Low': row['Low'],
                    'Close': row['Close'],
                    'Volume': row['Volume']
                }
                insert_data_into_db(data, connection)
        finally:
            # Ensure connection is closed after batch processing
            connection.close()

query = parsed_df.writeStream \
    .outputMode("append") \
    .foreachBatch(write_to_postgresql) \
    .option("checkpointLocation", "/tmp/checkpoints/historical_financial_data") \
    .start()

query.awaitTermination()