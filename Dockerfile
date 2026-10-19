FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/data \
    PORT=6969

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN groupadd --gid 1000 caleroo \
    && useradd --uid 1000 --gid 1000 --no-create-home caleroo \
    && mkdir -p /data \
    && chown caleroo:caleroo /data

USER caleroo

EXPOSE 6969

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
