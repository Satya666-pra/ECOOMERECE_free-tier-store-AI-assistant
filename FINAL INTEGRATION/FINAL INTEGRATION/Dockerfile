# Build the Application
FROM python:3.11-slim
WORKDIR /app

# uv — fast Python package installer (astral.sh/uv)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install backend dependencies
COPY requirements.txt .
RUN uv pip install --system --no-cache-dir -r requirements.txt

# Copy source code (Backend + Frontend natively)
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1

# Default port for local `docker run`; Render injects its own $PORT at runtime.
EXPOSE 8000

# Start the application. Shell form so ${PORT} is expanded: Render sets PORT,
# local Docker falls back to 8000.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
