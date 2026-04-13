FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libcairo2-dev \
    libffi-dev \
    libgdk-pixbuf-2.0-dev \
    libjpeg62-turbo-dev \
    libpango1.0-dev \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    shared-mime-info \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /app/requirements.txt

RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /app/requirements.txt


FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=horilla.settings \
    PORT=8000 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    dumb-init \
    fonts-dejavu-core \
    libcairo2 \
    libffi8 \
    libgdk-pixbuf-2.0-0 \
    libjpeg62-turbo \
    libpango-1.0-0 \
    libpq5 \
    libxml2 \
    libxslt1.1 \
    shared-mime-info \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --ingroup app --home /app app

COPY --from=builder /opt/venv /opt/venv
COPY . /app

RUN mkdir -p /app/staticfiles /app/media && \
    chmod +x /app/.docker/entrypoint.sh && \
    chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=3)" || exit 1

ENTRYPOINT ["/usr/bin/dumb-init", "--", "/app/.docker/entrypoint.sh"]
CMD []
