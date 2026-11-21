FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv/dossier

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app ./app

# Durable state lives on the container filesystem (Rul-S3-2); the path can be overridden.
RUN mkdir -p /srv/dossier/data
ENV DOSSIER_DATA_DIR=/srv/dossier/data

ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "app"]
