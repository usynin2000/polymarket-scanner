# Polymarket Scanner - Production Dockerfile
# Multi-stage build for smaller image size

FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml ./

COPY pyproject.toml README.md LICENSE ./

# Create virtual environment and install dependencies
RUN uv venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
RUN uv pip install --no-cache .

# --- Production Stage ---
FROM python:3.12-slim AS production

# Create non-root user for security
RUN groupadd --gid 1000 scanner \
    && useradd --uid 1000 --gid scanner --shell /bin/bash --create-home scanner

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY --chown=scanner:scanner scanner/ ./scanner/

# Switch to non-root user
USER scanner

# Health check - verify Python can import the module
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from scanner.main import main; print('OK')" || exit 1

# Default environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SCANNER_LOG_LEVEL=INFO

# Run the scanner
# Use --live for real Polymarket data, remove for mock mode
ENTRYPOINT ["python", "-m", "scanner.main"]
CMD ["--live"]

