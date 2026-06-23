FROM python:3.11-slim

# Métadonnées
LABEL maintainer="SOC Platform"
LABEL description="Backend FastAPI — SOC Platform"

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source — placé dans le package /app/api pour que `import api.*` résolve
# (l'app utilise des imports absolus `from api.xxx`). WORKDIR /app reste sur le
# sys.path, donc uvicorn lance api.main:app correctement.
COPY . ./api/

# Utilisateur non-root pour la sécurité
RUN adduser --disabled-password --gecos '' socapi && \
    chown -R socapi:socapi /app
USER socapi

# Port et commande
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--log-level", "info"]
