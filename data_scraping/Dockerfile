# Use the official Python 3.11 slim image as the base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Update package lists and install PostgreSQL development libraries (required for psycopg2)
RUN apt-get update && apt-get install -y libpq-dev

# Copy the requirements file into the container
COPY requirements.txt requirements.txt

# Upgrade pip and install all dependencies from the requirements file
RUN pip install --timeout=120 --upgrade pip && pip install -r requirements.txt

# Copy all project files into the container
COPY . .
