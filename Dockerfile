FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl -fsSL "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" -o /usr/local/bin/kubectl \
    && chmod +x /usr/local/bin/kubectl \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

COPY k8s_assistant ./k8s_assistant
COPY dashboard ./dashboard
COPY README.md ./

RUN useradd --create-home --uid 10001 assistant
USER assistant

EXPOSE 8080
CMD ["python", "-m", "k8s_assistant.cli", "serve", "--host", "0.0.0.0", "--port", "8080"]
