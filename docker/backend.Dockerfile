FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend /app/backend
COPY agent /app/agent
COPY database /app/database
# The app user must be able to read the code whatever permissions the checkout gave it; it still cannot write it.
RUN chmod -R a+rX /app/backend /app/agent /app/database && useradd --create-home --uid 10001 missioncontrol
USER missioncontrol
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
