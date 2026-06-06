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
RUN groupadd -g 10001 thaumio && \
    useradd -u 10001 -g thaumio -m -s /sbin/nologin thaumio

# Copy installed python dependencies from builder stage
COPY --from=builder /root/.local /home/thaumio/.local
ENV PATH=/home/thaumio/.local/bin:$PATH

# Copy application code
COPY --chown=thaumio:thaumio thaumio/ ./thaumio/
COPY --chown=thaumio:thaumio config/ ./config/

# Pre-create directory for data output mount with correct ownership
RUN mkdir -p /app/data /app/certs && \
    chown -R thaumio:thaumio /app

# Expose the FastAPI Control Plane REST API port
EXPOSE 8081

# Define standard mount points for configurations, certificates and local data sinks
VOLUME ["/app/config", "/app/certs", "/app/data"]

# Switch to the non-privileged user
USER thaumio

# Run the simulation engine with configurations
ENTRYPOINT ["python", "-m", "thaumio.main", "run"]
CMD ["--config", "config/topology_config.json"]
