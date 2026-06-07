FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY gerar_reel.py servidor.py ./
ENV OUTDIR=/data
RUN mkdir -p /data
EXPOSE 8080
CMD ["uvicorn", "servidor:app", "--host", "0.0.0.0", "--port", "8080"]
