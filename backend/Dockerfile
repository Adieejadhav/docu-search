FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    HF_HOME=/home/appuser/.cache/huggingface

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system appuser \
    && useradd --system --gid appuser --home-dir /home/appuser --create-home appuser

COPY pyproject.toml ./

RUN python -c "import pathlib,tomllib; pathlib.Path('/tmp/requirements.txt').write_text('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" \
    && pip install --retries 10 --timeout 120 -r /tmp/requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY README.md ./

RUN pip install --no-deps .

RUN mkdir -p /storage/uploads /home/appuser/.cache/huggingface \
    && chown -R appuser:appuser /app /storage /home/appuser

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
