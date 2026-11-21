FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
# One --prefix directory lets the runtime stage take the packages as a whole
# without the pip cache or any build tooling.
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-slim

# pg_isready, which entrypoint.sh uses to wait for the database.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 appuser

# The code stays root-owned, so the unprivileged process cannot rewrite it and
# cannot write bytecode next to it either. Unbuffered output keeps container
# logs in order and free of delay.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder /install /usr/local

WORKDIR /app
COPY . .
RUN baml-cli generate

# Strip any CR (defends against a CRLF checkout on Windows) and make the script
# executable so the shebang resolves inside the container.
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()"

ENTRYPOINT ["/entrypoint.sh"]

# Uvicorn's access log prints the client address and query string unstructured;
# the structured http.request log from the logging middleware replaces it.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
