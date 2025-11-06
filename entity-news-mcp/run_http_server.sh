#!/bin/bash
# Run the HTTP server for OpenAI Agent Builder

echo "Starting Entity News MCP HTTP Server..."
echo "Server will be available at: http://localhost:8000"
echo ""
echo "For OpenAI Agent Builder:"
echo "  - Local: Use http://localhost:8000"
echo "  - Production: Deploy with HTTPS or use ngrok for tunneling"
echo ""

uv run python http_server.py

