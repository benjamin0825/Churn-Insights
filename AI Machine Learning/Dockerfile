# CPU-only image for training jobs and the prediction API.
# Python 3.14: the bundled native engine (src/churn_ml/_native) is built for CPython 3.14
FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MLFLOW_DISABLE_AGENT_HINT=1

# libgomp is needed by LightGBM/XGBoost; gcc compiles churn_ml._kernels_ext when its source exists
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml setup.py README.md ./
COPY configs ./configs
COPY src ./src
RUN pip install . \
    && python -c "import churn_ml.kernels as k; print('kernel backend:', k.BACKEND)"

# Artifacts (raw data, features, registry, MLflow db) live on a volume.
VOLUME ["/app/artifacts"]
EXPOSE 8000

RUN useradd --create-home app && chown -R app /app
USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

ENTRYPOINT ["churn-ml"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
