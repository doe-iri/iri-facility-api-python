FROM python:3.13

RUN mkdir /app
COPY . /app
WORKDIR /app

RUN pip install -U pip wheel setuptools uv && \
    uv pip install --system .

ENV IRI_API_ADAPTER_account="app.s3df.account_adapter.S3DFAccountAdapter"
ENV IRI_SHOW_MISSING_ROUTES="true"
ENV DEX_JWKS_URL="https://dex.slac.stanford.edu/keys"
ENV DEX_ISSUER="https://dex.slac.stanford.edu"


CMD ["fastapi", "run", "app/main.py", "--port", "8000"]
