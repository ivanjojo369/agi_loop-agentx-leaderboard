FROM python:3.11-slim

# 1) Dependencias del sistema: curl (por healthcheck) + CA certs
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) Variables útiles
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 3) Instala deps Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4) Copia código
COPY app ./app
COPY run-agentbeats /usr/local/bin/run-agentbeats

# 5) Limpia CRLF y permisos
RUN sed -i 's/\r$//' /usr/local/bin/run-agentbeats /app/app/server.py && \
    chmod +x /usr/local/bin/run-agentbeats

# 6) EntryPoint robusto (sin depender de shebang)
ENTRYPOINT ["python3", "/usr/local/bin/run-agentbeats"]
CMD []
