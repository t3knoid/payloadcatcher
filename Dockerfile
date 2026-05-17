FROM node:20.19.0-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements.txt
COPY requirements-dev.txt requirements-dev.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY alembic.ini alembic.ini
COPY alembic alembic
COPY app app
COPY frontend/src frontend/src
COPY frontend/index.html frontend/index.html
COPY frontend/package.json frontend/package.json
COPY frontend/tsconfig.app.json frontend/tsconfig.app.json
COPY frontend/tsconfig.json frontend/tsconfig.json
COPY frontend/tsconfig.node.json frontend/tsconfig.node.json
COPY frontend/vite.config.ts frontend/vite.config.ts
COPY --from=frontend-build /frontend/dist frontend/dist

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
