FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev

COPY requirements.txt requirements.txt

RUN pip install --timeout=120 --upgrade pip && pip install -r requirements.txt

COPY . .
