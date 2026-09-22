# syntax=docker/dockerfile:1
FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY xlcompiler/ ./xlcompiler/
COPY workbook/ ./workbook/


RUN python -c "import sys; sys.path.insert(0, 'xlcompiler'); \
from compiler.workbook_model import WorkbookModel; \
m = WorkbookModel.load('workbook/IESS2047_Version_3.0.xlsx'); \
print(f'pickle built: {len(m.cells)} cells, {len(m.tables)} tables')"


COPY ui/ ./ui/
COPY tools/ ./tools/
COPY cache/ ./cache/
COPY wsgi.py .


RUN useradd --create-home --uid 10001 appuser \
 && mkdir -p /app/cache/pathways \
 && chown -R appuser:appuser /app
USER appuser


ENV IESS_RATE_LIMIT_MAX=3000 \
    IESS_CACHE_DIR=/app/cache/pathways


EXPOSE 5051


HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,os,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','5051')+'/cache_stats', timeout=4).status==200 else 1)"


# exec form + explicit `sh -c` keeps ${PORT} expansion (needed by Fly/Render/
# Cloud Run) while `exec` makes gunicorn PID 1, so docker stop's SIGTERM
# reaches it and --graceful-timeout actually applies.
# WEB_CONCURRENCY = worker PROCESSES. 4 by default, and the count matters a lot:
#   1 worker  -> a cold 0.8s compute is pure-Python CPU work that holds the GIL,
#                so it freezes the threads serving 2ms cache hits too. Measured
#                at 30 users, 10% cold: cached clicks degraded to p95 2161ms.
#   4 workers -> separate interpreters, separate GILs. Same test: p95 56ms,
#                throughput 16.8 -> 34.6 req/s.
# Each worker loads its own ~400 MB copy of the model, so 4 needs ~2 GB. On a
# 1 GB host set WEB_CONCURRENCY=2 (or 1) at run time -- no rebuild needed.
# The per-process baseline memo that multiple workers would otherwise break is
# handled by wsgi.py's preset warm; see the long note there.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-5051} --worker-class gthread --workers ${WEB_CONCURRENCY:-4} --threads 4 --timeout 120 --graceful-timeout 30 --access-logfile - --error-logfile - wsgi:app"]
