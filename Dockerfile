# ============================================================
# Ombre Brain Docker Build (Railway test — dual-process)
# ============================================================

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .
COPY heartcore_state.json .
COPY heartcore ./heartcore
COPY desire ./desire
COPY resources ./resources
COPY scripts ./scripts
COPY dashboard.html .
COPY config.yaml ./config.yaml
COPY start.sh .
RUN chmod +x scripts/*.sh
RUN chmod +x start.sh

ENV OMBRE_TRANSPORT=streamable-http
ENV OMBRE_BUCKETS_DIR=/data
ENV OMBRE_STATE_DIR=/data/state

EXPOSE 8000 8010

CMD ["bash", "start.sh"]
