FROM python:3.12-slim

# Install Node.js for MCP servers (npx @mongodb-js/mongodb-mcp-server, etc.)
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-install MCP servers to speed up container start
RUN npx -y @mongodb-js/mongodb-mcp-server --version || true

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
