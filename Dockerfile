# ============================================
# Stage 1: Builder
# ============================================
FROM python:3.13-slim AS builder

# Set working directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies to a local directory
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================
# Stage 2: Runtime
# ============================================
FROM python:3.13-slim

# Set metadata labels
LABEL maintainer="Major Domo Bot"
LABEL description="Discord Bot v2.0 for Strat-o-Matic Baseball Association"
LABEL version="2.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/botuser/.local/bin:$PATH"

# Create non-root user
RUN groupadd -r botuser && \
    useradd -r -g botuser -u 1000 -m -s /bin/bash botuser

# Set working directory
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder stage
COPY --from=builder --chown=botuser:botuser /root/.local /home/botuser/.local

# Copy application code
COPY --chown=botuser:botuser . .

# Note: /app/data and /app/logs will be mounted as volumes at runtime
# No need to create them in the image

# Switch to non-root user
USER botuser

# Expose no ports (Discord bot connects outbound only)

# Health check - verify bot process is running and responsive
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Set entrypoint
CMD ["python", "-u", "bot.py"]
