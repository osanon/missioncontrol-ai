FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt pytest==9.1.1
COPY backend /app/backend
COPY agent /app/agent
COPY database /app/database
COPY tests /app/tests
COPY pytest.ini /app/pytest.ini
CMD ["python", "-m", "pytest", "-q"]
