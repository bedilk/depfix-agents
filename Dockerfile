# =============================================================================
#  depfix — application container
#  Multi-stage build: install deps in a builder, then copy to a slim runtime.
# =============================================================================

ARG PYTHON_VERSION=3.11

# ---- builder ----------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps only needed at build time
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
COPY src ./src

RUN pip install --prefix=/install -r requirements.txt \
 && pip install --prefix=/install --no-deps .

# ---- runtime ----------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:${PATH}" \
    PYTHONPATH="/install/lib/python3.11/site-packages"

# Node.js is used by the JS syntax validator
RUN apt-get update && apt-get install -y --no-install-recommends \
        nodejs \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd --create-home --uid 1001 depfix
WORKDIR /app

COPY --from=builder /install /install
COPY --from=builder /app/src /app/src

USER depfix

# Default: show help. Override with `docker run ... depfix --codebase /work`
ENTRYPOINT ["depfix"]
CMD ["--help"]
