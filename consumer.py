from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, avg, to_timestamp
from pyspark.sql.types import StructType, StructField, StringType, DoubleType

# Kafka Configuration
KAFKA_BROKER = "localhost:9092"
KAFKA_TOPIC = "financial_data"

# Define Spark Session
spark = SparkSession.builder \
    .appName("StockDataProcessing") \
    .master("local[*]") \
    .config("spark.sql.shuffle.partitions", "10") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0") \
    .getOrCreate()

# Define Schema for Incoming Data
schema = StructType([
    StructField("Date", StringType(), True),
    StructField("Symbol", StringType(), True),
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

# Convert Date to proper timestamp type
parsed_df = parsed_df.withColumn("Date", to_timestamp(col("Date"), "yyyy-MM-dd HH:mm:ssXXX"))


# Add Watermark (important for streaming aggregations)
parsed_df = parsed_df.withWatermark("Date", "10 minutes")

# Filter out invalid data
parsed_df = parsed_df.filter(
    col("Symbol").isNotNull() &
    col("Open").isNotNull() &
    col("High").isNotNull() &
    col("Low").isNotNull() &
    col("Close").isNotNull() &
    col("Volume").isNotNull()
)

# Data Processing: Compute Average Prices by Symbol
avg_prices = parsed_df.groupBy("Symbol").agg(
    avg("Open").alias("avg_open"),
    avg("High").alias("avg_high"),
    avg("Low").alias("avg_low"),
    avg("Close").alias("avg_close"),
    avg("Volume").alias("avg_volume")
)

# Write price averages to console with batching
query = avg_prices.writeStream \
    .outputMode("update") \
    .format("console") \
    .option("truncate", False) \
    .option("checkpointLocation", "checkpoint/financial_data") \
    .start()

query.awaitTermination()




