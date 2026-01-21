FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src

# The -u flag makes python output unbuffered, so you see logs immediately
CMD ["python", "-u", "src/main.py"]