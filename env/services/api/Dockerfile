FROM python:3.13-slim
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" psycopg2-binary
WORKDIR /srv
COPY app.py /srv/app.py
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]