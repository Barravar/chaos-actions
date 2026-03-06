ARG PY_VERSION=3.12
ARG BASE_IMAGE=${PY_VERSION}-alpine
# Builder stage to install dependencies
FROM python:${BASE_IMAGE} AS builder

WORKDIR /build

RUN apk add --no-cache gcc musl-dev libffi-dev

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt --target=/dependencies

# Final stage for production image
FROM python:${BASE_IMAGE}
ARG PY_VERSION
ARG VERSION=1.0.0

LABEL name="Litmus Chaos Actions" \
      maintainer="Barravar Inc. <barravar@barravar.com.br>" \
      repository="https://github.com/Barravar/chaos-actions" \
      description="Chaos engineering actions for Kubernetes" \
      version="${VERSION}"

# Python optimization environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/chaos-actions \
    PATH="/chaos-actions/.local/bin:$PATH"

WORKDIR /chaos-actions

# Create non-root user
RUN addgroup -g 1000 chaosuser && \
    adduser -D -u 1000 -G chaosuser chaosuser && \
    chown -R chaosuser:chaosuser /chaos-actions

COPY --from=builder --chown=chaosuser:chaosuser /dependencies /usr/local/lib/python${PY_VERSION}/site-packages/

# Copy application files as non-root user
COPY --chown=chaosuser:chaosuser src/ ./src/

USER chaosuser

# Run the application
ENTRYPOINT ["python", "-m", "src.main"]
