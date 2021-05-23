FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8

WORKDIR /app

RUN pip install poetry

COPY poetry.lock pyproject.toml ./
COPY twitscrape /app/twitscrape

RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi

EXPOSE 8000
ENTRYPOINT ["twitscrape"]
