# Entity News MCP Server

A Model Context Protocol (MCP) server that provides news articles for entities using NewsAPI and GNews.

## Features

- Get news articles for any entity
- Combines results from multiple news sources
- Available via stdio (for Claude Desktop) and HTTP (for OpenAI Agent Builder)

## Setup

1. Install dependencies:
```bash
uv sync
```

2. Make sure you have API keys configured in `utils.py`:
   - NewsAPI key (get one at https://newsapi.org)
   - GNews API key (if required)

## Running the Server

### Option 1: MCP Server (stdio) - for Claude Desktop

```bash
uv run mcp dev server.py
```

### Option 2: HTTP Server - for OpenAI Agent Builder

```bash
uv run python http_server.py
```

The HTTP server will start on `http://localhost:8000`

## HTTP Endpoints

### Health Check
- `GET /` - Server status and info
- `GET /health` - Health check

### Tools
- `POST /tools/get_entity_news` - Get news articles for an entity
  ```json
  {
    "entity_name": "Apple"
  }
  ```

- `GET /tools/list` - List all available tools

### MCP Protocol Endpoints
- `POST /mcp/tools/call` - MCP protocol tool call
- `GET /mcp/tools/list` - List tools in MCP format

## Connecting to OpenAI Agent Builder

1. **For Local Development (HTTP):**
   - Start the HTTP server: `uv run python http_server.py`
   - Use URL: `http://localhost:8000`
   - Note: Agent Builder may require HTTPS in production

2. **For Production (HTTPS):**
   - Deploy the server to a platform that provides HTTPS (e.g., Railway, Render, Fly.io)
   - Or use a reverse proxy like nginx with SSL certificates
   - Use the HTTPS URL in Agent Builder

## Example Usage

### Using HTTP API directly:

```bash
curl -X POST http://localhost:8000/tools/get_entity_news \
  -H "Content-Type: application/json" \
  -d '{"entity_name": "Apple"}'
```

### Using MCP Protocol:

```bash
curl -X POST http://localhost:8000/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_entity_news",
    "arguments": {"entity_name": "Apple"}
  }'
```

## Connecting to Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "entity-news": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/kiranhegde_personal/Documents/AiTradingSignals/entity-news-mcp",
        "mcp",
        "run",
        "server.py"
      ]
    }
  }
}
```

## Project Structure

- `server.py` - MCP server (stdio) for Claude Desktop
- `http_server.py` - HTTP wrapper for OpenAI Agent Builder
- `utils.py` - News fetching utilities
- `main.py` - Entry point (if needed)

