# Nabız Analiz (Python). Ayrıntı: docs/SUNUCU_KURULUMU.md
#   docker build -t nabiz-analiz .
# Bağımlılıklar requirements.txt'te sürüm VE özet (hash) ile sabit: pip başka bir dosya indirirse kurulum durur.
FROM python:3.15.1-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PORT=8000
WORKDIR /app
COPY requirements.txt ./
RUN pip install --require-hashes --no-deps -r requirements.txt
COPY analiz ./analiz
RUN useradd --system --uid 10001 --no-create-home analiz
USER analiz
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/healthz', timeout=4).status==200 else 1)"
CMD ["python", "-m", "analiz"]
