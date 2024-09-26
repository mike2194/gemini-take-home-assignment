FROM docker.io/python:3.12-bookworm

WORKDIR /app

ADD . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["python", "/app/apiAlerts.py"]
