FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 moneygraph \
    && useradd --uid 10001 --gid moneygraph --create-home moneygraph \
    && mkdir -p /app/out \
    && chown moneygraph:moneygraph /app/out

COPY --chown=moneygraph:moneygraph . .
USER moneygraph
EXPOSE 8501

CMD ["python", "-m", "streamlit", "run", "app/app.py", "--server.address=0.0.0.0", "--server.headless=true", "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
