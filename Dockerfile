FROM python:3.12-slim

WORKDIR /app
COPY dashboard.py .

RUN useradd -r -u 1000 -m dashboard && mkdir -p /data && chown dashboard:dashboard /data
USER dashboard

ENV DATA_DIR=/data \
    DASHBOARD_PORT=8765

EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('DASHBOARD_PORT','8765')+'/api/status')"

CMD ["python3", "-u", "dashboard.py"]
