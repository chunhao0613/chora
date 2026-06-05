# Stage 1: Build & install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Final minimal runtime
FROM python:3.11-slim AS runner

WORKDIR /app

# Create a non-privileged system user for security
RUN groupadd -g 10001 chora && \
    useradd -u 10001 -g chora -m -s /sbin/nologin chora

# Copy installed python dependencies from builder stage
COPY --from=builder /root/.local /home/chora/.local
ENV PATH=/home/chora/.local/bin:$PATH

# Copy application code
COPY --chown=chora:chora src/ ./src/
COPY --chown=chora:chora config/ ./config/

# Pre-create directory for data output mount with correct ownership
RUN mkdir -p /app/data /app/certs && \
    chown -R chora:chora /app

# Expose the FastAPI Control Plane REST API port
EXPOSE 8081

# Define standard mount points for configurations, certificates and local data sinks
VOLUME ["/app/config", "/app/certs", "/app/data"]

# Switch to the non-privileged user
USER chora

# Run the simulation engine with configurations
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--config", "config/topology_config.json"]
