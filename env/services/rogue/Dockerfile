FROM python:3.13-slim
RUN pip install --no-cache-dir psycopg2-binary
WORKDIR /srv
COPY app.py /srv/app.py
CMD ["python", "app.py"]