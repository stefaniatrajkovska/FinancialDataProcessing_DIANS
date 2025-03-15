# import logging
# import psycopg2
# from pyspark.sql import SparkSession
# from pyspark.sql.functions import from_json, col, avg
# from pyspark.sql.types import StructType, StructField, StringType, DoubleType
#
# # Kafka Configuration
# KAFKA_BROKER = "localhost:9092"
# KAFKA_TOPIC = "financial_data"
#
# DB_HOST = "localhost"
# DB_PORT = "5432"
# DB_NAME = "financial_data_db"
# DB_USER = "postgres"
# DB_PASSWORD = "financialdataproject"
#
# def connect_to_db():
#     try:
#         connection = psycopg2.connect(
#             host=DB_HOST,
#             port=DB_PORT,
#             database=DB_NAME,
#             user=DB_USER,
#             password=DB_PASSWORD
#         )
#         logging.info("Successfully connected to PostgreSQL database.")
#         return connection
#     except Exception as e:
#         logging.error(f"Error connecting to PostgreSQL database: {e}")
#         return None
#
#
# def insert_data_into_db(data):
#     connection = connect_to_db()
#     if connection:
#         try:
#             cursor = connection.cursor()
#
#             # SQL INSERT query
#             insert_query = """
#             INSERT INTO financial_data (symbol, open, high, low, close, volume)
#             VALUES (%s, %s, %s, %s, %s, %s)
#             """
#
#             # Податоците од Kafka (data треба да содржи сите потребни информации)
#             cursor.execute(insert_query, (
#                 data['Symbol'],
#                 data['Open'],
#                 data['High'],
#                 data['Low'],
#                 data['Close'],
#                 data['Volume']
#             ))
#
#             # Потврда и затворање на курсорот и врската
#             connection.commit()
#             cursor.close()
#             logging.info(f"Data for symbol {data['Symbol']} successfully inserted into the database.")
#
#         except Exception as e:
#             logging.error(f"Error inserting data into the database: {e}")
#         finally:
#             connection.close()
#
# # Define Spark Session
# spark = SparkSession.builder \
#     .appName("StockDataProcessing") \
#     .master("local[*]") \
#     .config("spark.sql.shuffle.partitions", "10") \
#     .config("spark.jars.packages", "org.postgresql:postgresql:42.7.2") \
#     .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0") \
#     .getOrCreate()
#
# # Define Schema for Incoming Data
# schema = StructType([
#     StructField("Symbol", StringType(), True),
#     StructField("Date", StringType(), True),
#     StructField("Open", DoubleType(), True),
#     StructField("High", DoubleType(), True),
#     StructField("Low", DoubleType(), True),
#     StructField("Close", DoubleType(), True),
#     StructField("Volume", DoubleType(), True)
# ])
#
# # Read Data from Kafka
# raw_stream = spark.readStream \
#     .format("kafka") \
#     .option("kafka.bootstrap.servers", KAFKA_BROKER) \
#     .option("subscribe", KAFKA_TOPIC) \
#     .option("startingOffsets", "latest") \
#     .load()
#
# # Deserialize JSON Data
# df = raw_stream.selectExpr("CAST(key AS STRING) as symbol_key", "CAST(value AS STRING) as json_data")
# parsed_df = df.select(
#     col("symbol_key"),
#     from_json(col("json_data"), schema).alias("data")
# ).select("symbol_key", "data.*")
#
# # Filter out invalid data
# parsed_df = parsed_df.filter(
#     col("Symbol").isNotNull() &
#     col("Open").isNotNull() &
#     col("High").isNotNull() &
#     col("Low").isNotNull() &
#     col("Close").isNotNull() &
#     col("Volume").isNotNull()
# )
#
# # Data Processing: Compute Average Prices by Symbol
# avg_prices = parsed_df.groupBy("Symbol").agg(
#     avg("Open").alias("avg_open"),
#     avg("High").alias("avg_high"),
#     avg("Low").alias("avg_low"),
#     avg("Close").alias("avg_close"),
#     avg("Volume").alias("avg_volume")
# )
#
# def write_to_postgresql(batch_df, batch_id):
#     for row in batch_df.collect():
#         data = {
#             'Symbol': row['Symbol'],
#             'Open': row['avg_open'],
#             'High': row['avg_high'],
#             'Low': row['avg_low'],
#             'Close': row['avg_close'],
#             'Volume': row['avg_volume']
#         }
#         insert_data_into_db(data)
#
# # Write price averages to console with batching
# query = avg_prices.writeStream \
#     .outputMode("update") \
#     .foreachBatch(write_to_postgresql) \
#     .option("truncate", False) \
#     .option("checkpointLocation", "checkpoint/financial_data") \
#     .start()
#
# query.awaitTermination()





import logging
import psycopg2
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType, DoubleType

# Kafka Configuration
KAFKA_BROKER = "localhost:9092"
KAFKA_TOPIC = "financial_data"

DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "financial_data_db"
DB_USER = "postgres"
DB_PASSWORD = "financialdataproject"

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


def insert_data_into_db(data):
    connection = connect_to_db()
    if connection:
        try:
            cursor = connection.cursor()

            # SQL INSERT query
            insert_query = """
            INSERT INTO financial_data (symbol, date, open, high, low, close, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """

            # Podatocite od Kafka (data treba da sodrzi site potrebni informacii)
            cursor.execute(insert_query, (
                data['Symbol'],
                data['Date'],
                data['Open'],
                data['High'],
                data['Low'],
                data['Close'],
                data['Volume']
            ))

            # Potvrda i zatvoranje na kursorot i vrskata
            connection.commit()
            cursor.close()
            logging.info(f"Data for symbol {data['Symbol']} and date {data['Date']} successfully inserted into the database.")

        except Exception as e:
            logging.error(f"Error inserting data into the database: {e}")
        finally:
            connection.close()

# Define Spark Session
spark = SparkSession.builder \
    .appName("StockDataProcessing") \
    .master("local[*]") \
    .config("spark.sql.shuffle.partitions", "10") \
    .config("spark.jars.packages", "org.postgresql:postgresql:42.7.2") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0") \
    .getOrCreate()

# Define Schema for Incoming Data
schema = StructType([
    StructField("Symbol", StringType(), True),
    StructField("Date", StringType(), True),
    StructField("Open", DoubleType(), True),
    StructField("High", DoubleType(), True),
    StructField("Low", DoubleType(), True),
    StructField("Close", DoubleType(), True),
    StructField("Volume", DoubleType(), True)
])

# Read Data from Kafka
raw_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC) \
    .option("startingOffsets", "latest") \
    .load()

# Deserialize JSON Data
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

def write_to_postgresql(batch_df, batch_id):
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
        insert_data_into_db(data)

# Write raw data to console with batching
query = parsed_df.writeStream \
    .outputMode("append") \
    .foreachBatch(write_to_postgresql) \
    .option("truncate", False) \
    .option("checkpointLocation", "checkpoint/financial_data") \
    .start()

query.awaitTermination()
