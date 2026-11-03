# syntax=docker/dockerfile:1
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AIU_DATA_DIR=/data
WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN --mount=type=secret,id=proxy_ca,required=false \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    python -m pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
RUN chmod -R a+rX /app/backend \
    && groupadd --gid 10001 aiu && useradd --uid 10001 --gid aiu --no-create-home aiu \
    && mkdir /data && chown aiu:aiu /data
USER aiu
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
