FROM python:3

RUN mkdir /app
COPY . /app
WORKDIR /app

RUN pip install -U pip
RUN pip install -U wheel
RUN pip install -U setuptools
RUN pip install uv
RUN uv pip install --system -r /app/pyproject.toml

CMD ["fastapi", "run", "app/main.py", "--port", "8000"]
