FROM python:3.11-slim

# Install required system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    tar \
    gzip \
    ca-certificates \
    curl \
    procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Download and install OpenJDK 11
RUN mkdir -p /opt/java \
    && wget -q https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.22%2B7/OpenJDK11U-jdk_x64_linux_hotspot_11.0.22_7.tar.gz -O /tmp/openjdk.tar.gz \
    && tar -xzf /tmp/openjdk.tar.gz -C /opt/java \
    && rm /tmp/openjdk.tar.gz \
    && ln -s /opt/java/jdk-11.0.22+7 /opt/java/current

# Set Java environment variables
ENV JAVA_HOME=/opt/java/current
ENV PATH=$JAVA_HOME/bin:$PATH

# Set Spark version
ARG SPARK_VERSION=3.3.0
ARG HADOOP_VERSION=3

# Download and install Apache Spark
RUN mkdir -p /opt/spark \
    && curl -fsSL https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz \
    | tar -xz -C /opt/spark --strip-components=1

# Set Spark environment variables
ENV SPARK_HOME=/opt/spark
ENV PATH=$SPARK_HOME/bin:$PATH
ENV PYTHONPATH=$SPARK_HOME/python:$PYTHONPATH
ENV PYSPARK_PYTHON=python3
ENV PYSPARK_DRIVER_PYTHON=python3

# Create directory for drivers
RUN mkdir -p /drivers

# Download PostgreSQL JDBC driver
RUN curl -o /drivers/postgresql-42.7.2.jar https://jdbc.postgresql.org/download/postgresql-42.7.2.jar

# Set Spark classpath to include PostgreSQL driver
ENV SPARK_CLASSPATH="/drivers/postgresql-42.7.2.jar"

# Install Python dependencies
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --timeout=120 --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .





