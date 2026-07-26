FROM python:3.13-slim

WORKDIR /app

# install deps first (cached layer unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy the rest of the app
COPY . .

# create the data dir in case it doesn't exist
RUN mkdir -p data/sample_docs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
