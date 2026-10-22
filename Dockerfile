FROM python:3.13-slim

# Logs inmediatos, sin buffer.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Primero las dependencias: si solo cambia el código, Docker reutiliza esta capa y el build tarda segundos.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Solo se copia el código y las migraciones: nada más del repositorio (como un .env) entra en la imagen.
COPY app/ app/
COPY migrations/ migrations/

# La API no corre como root.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Una sola definición de "sano" para compose, CI y el despliegue: /health tiene que responder 200.
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

# Primero migra y después atiende. Con exec, uvicorn recibe la señal de apagado y se detiene limpio.
CMD ["sh", "-c", "python -m app.migrate && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
