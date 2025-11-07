"""
HTTP Wrapper for MCP Server
Exposes MCP tools via HTTP/HTTPS for OpenAI Agent Builder
Implements MCP protocol with JSON-RPC 2.0 and SSE support
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import json
import uuid
import asyncio
import logging
import time
import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from utils import get_entity_news_from_api, get_entity_news_from_gnews

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Timeout middleware to track request processing time
class TimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        
        # Log request start
        logger.info(f"[{request_id}] {request.method} {request.url.path} - START")
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(round(process_time, 3))
            response.headers["X-Request-ID"] = request_id
            
            # Log completion
            logger.info(f"[{request_id}] {request.method} {request.url.path} - COMPLETE in {process_time:.3f}s (Status: {response.status_code})")
            
            # Warn if request took too long
            if process_time > 10:
                logger.warning(f"[{request_id}] SLOW REQUEST: {process_time:.3f}s")
            if process_time > 30:
                logger.error(f"[{request_id}] VERY SLOW REQUEST: {process_time:.3f}s - May timeout!")
            
            return response
        except asyncio.TimeoutError as e:
            process_time = time.time() - start_time
            logger.error(f"[{request_id}] TIMEOUT after {process_time:.3f}s: {e}")
            raise
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"[{request_id}] ERROR after {process_time:.3f}s: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"[{request_id}] Traceback: {traceback.format_exc()}")
            raise


def _get_entity_news(entity_name: str) -> List[Dict[str, Any]]:
    """Helper function to fetch news from all sources (synchronous)."""
    start_time = time.time()
    list1 = get_entity_news_from_api(entity_name)
    api_time = time.time() - start_time
    logger.info(f"NewsAPI call took {api_time:.3f}s")
    
    start_time = time.time()
    list2 = get_entity_news_from_gnews(entity_name)
    gnews_time = time.time() - start_time
    logger.info(f"GNews call took {gnews_time:.3f}s")
    
    total_time = api_time + gnews_time
    logger.info(f"Total news fetch took {total_time:.3f}s")
    return list1 + list2


async def _get_entity_news_async(entity_name: str) -> List[Dict[str, Any]]:
    """Async helper function to fetch news from all sources in parallel (faster)."""
    start_time = time.time()
    logger.info(f"Starting async news fetch for: {entity_name}")
    
    async def fetch_newsapi():
        """Fetch from NewsAPI"""
        api_start = time.time()
        try:
            logger.info(f"Fetching from NewsAPI for: {entity_name}")
            API_KEY = "48c51ab301094753bb46f899b6b5a103"
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': entity_name,
                'sortBy': 'publishedAt',
                'language': 'en',
                'pageSize': 10,
                'apiKey': API_KEY
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data.get('status') != 'ok':
                    logger.warning(f"NewsAPI Error: {data.get('message', 'Unknown error')}")
                    return []
                
                articles = []
                for article in data.get('articles', []):
                    articles.append({
                        'title': article.get('title', ''),
                        'url': article.get('url', ''),
                        'source': article.get('source', {}).get('name', ''),
                        'description': article.get('description'),
                        'published_at': article.get('publishedAt'),
                        'image': article.get('urlToImage')
                    })
                api_time = time.time() - api_start
                logger.info(f"NewsAPI completed in {api_time:.3f}s, returned {len(articles)} articles")
                return articles
        except asyncio.TimeoutError as e:
            api_time = time.time() - api_start
            logger.error(f"NewsAPI TIMEOUT after {api_time:.3f}s: {e}")
            return []
        except Exception as e:
            api_time = time.time() - api_start
            logger.error(f"Error fetching from NewsAPI after {api_time:.3f}s: {type(e).__name__}: {e}")
            return []
    
    async def fetch_gnews():
        """Fetch from GNews"""
        gnews_start = time.time()
        try:
            logger.info(f"Fetching from GNews for: {entity_name}")
            url = "https://gnews.io/api/v4/search"
            params = {
                'q': entity_name,
                'lang': 'en',
                'max': 10,
                'apikey': 'db2651be6ce35c4956fbe1fc2a5a8cdb'  # GNews API key
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                # GNews returns articles directly in the response
                articles = []
                for article in data.get('articles', []):
                    articles.append({
                        'title': article.get('title', ''),
                        'url': article.get('url', ''),
                        'source': article.get('source', {}).get('name', '') if isinstance(article.get('source'), dict) else article.get('source', ''),
                        'description': article.get('description'),
                        'published_at': article.get('publishedAt'),
                        'image': article.get('image')
                    })
                gnews_time = time.time() - gnews_start
                logger.info(f"GNews completed in {gnews_time:.3f}s, returned {len(articles)} articles")
                return articles
        except asyncio.TimeoutError as e:
            gnews_time = time.time() - gnews_start
            logger.error(f"GNews TIMEOUT after {gnews_time:.3f}s: {e}")
            return []
        except Exception as e:
            gnews_time = time.time() - gnews_start
            logger.error(f"Error fetching from GNews after {gnews_time:.3f}s: {type(e).__name__}: {e}")
            return []
    
    # Run both API calls in parallel with timeout
    try:
        list1, list2 = await asyncio.wait_for(
            asyncio.gather(
                fetch_newsapi(),
                fetch_gnews(),
                return_exceptions=True
            ),
            timeout=60.0  # Total timeout for both calls
        )
    except asyncio.TimeoutError:
        total_time = time.time() - start_time
        logger.error(f"TOTAL TIMEOUT after {total_time:.3f}s - Both API calls exceeded 60s")
        return []
    
    # Handle exceptions
    if isinstance(list1, Exception):
        logger.error(f"NewsAPI exception: {list1}")
        list1 = []
    if isinstance(list2, Exception):
        logger.error(f"GNews exception: {list2}")
        list2 = []
    
    total_time = time.time() - start_time
    total_articles = len(list1) + len(list2)
    logger.info(f"Async news fetch COMPLETE: {total_time:.3f}s (parallel) - {total_articles} total articles")
    
    if total_time > 30:
        logger.warning(f"SLOW: News fetch took {total_time:.3f}s - may cause client timeout")
    
    return list1 + list2


def _get_mcp_tool_list() -> Dict[str, Any]:
    """Helper function to get list of tools in MCP format."""
    return {
        "tools": [
            {
                "name": "get_entity_news",
                "description": "Get news articles for an entity",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "entity_name": {
                            "type": "string",
                            "description": "Name of the entity to search for"
                        }
                    },
                    "required": ["entity_name"]
                }
            }
        ]
    }


app = FastAPI(
    title="Entity News MCP Server",
    description="HTTP wrapper for Entity News MCP tools",
    version="0.1.0"
)

# Enable CORS for Agent Builder
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add timeout middleware
app.add_middleware(TimeoutMiddleware)


# Request/Response models
class ToolRequest(BaseModel):
    """Request model for tool calls"""
    entity_name: str


class NewsArticle(BaseModel):
    """News article model"""
    title: str
    url: str
    source: str
    description: Optional[str] = None
    published_at: Optional[str] = None
    image: Optional[str] = None


class ToolResponse(BaseModel):
    """Response model for tool calls"""
    success: bool
    data: List[Dict[str, Any]]
    error: Optional[str] = None


@app.get("/")
async def root():
    """Health check and MCP server info endpoint"""
    return {
        "status": "ok",
        "service": "Entity News MCP Server",
        "version": "0.1.0",
        "protocol": "mcp",
        "endpoints": {
            "mcp": "/mcp",
            "sse": "/sse",
            "health": "/health"
        },
        "tools": ["get_entity_news"]
    }


# Note: root_post will be defined after mcp_jsonrpc


# Note: Alternative endpoint paths can be added after mcp_jsonrpc is defined


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics():
    """Monitoring endpoint to check server status and recent performance"""
    try:
        import psutil
        import os
    except ImportError:
        return {
            "status": "running",
            "error": "psutil not installed - install with: uv add psutil",
            "timeouts": {
                "uvicorn_keep_alive": 300,
                "api_timeout": 30,
                "total_fetch_timeout": 60,
            },
            "timestamp": time.time()
        }
    
    process = psutil.Process(os.getpid())
    
    return {
        "status": "running",
        "server": {
            "uptime_seconds": time.time() - process.create_time(),
            "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
            "cpu_percent": process.cpu_percent(interval=0.1),
        },
        "timeouts": {
            "uvicorn_keep_alive": 300,
            "api_timeout": 30,
            "total_fetch_timeout": 60,
        },
        "timestamp": time.time()
    }


@app.post("/debug")
async def debug_endpoint(request: Request):
    """Debug endpoint to see what requests are being sent"""
    body = await request.body()
    headers = dict(request.headers)
    
    try:
        body_json = await request.json()
    except:
        body_json = body.decode('utf-8') if body else None
    
    return {
        "method": request.method,
        "url": str(request.url),
        "headers": headers,
        "body": body_json,
        "raw_body": body.decode('utf-8') if body else None
    }


@app.post("/tools/get_entity_news", response_model=ToolResponse)
async def get_entity_news_tool(request: ToolRequest):
    """
    Get news articles for an entity
    
    This endpoint wraps the MCP tool and exposes it via HTTP
    """
    try:
        result = await _get_entity_news_async(request.entity_name)
        return ToolResponse(
            success=True,
            data=result
        )
    except Exception as e:
        logger.error(f"Error in get_entity_news_tool: {e}")
        return ToolResponse(
            success=False,
            data=[],
            error=str(e)
        )


@app.get("/tools/list")
async def list_tools():
    """List all available tools"""
    return {
        "tools": [
            {
                "name": "get_entity_news",
                "description": "Get news articles for an entity",
                "endpoint": "/tools/get_entity_news",
                "method": "POST",
                "parameters": {
                    "entity_name": {
                        "type": "string",
                        "required": True,
                        "description": "Name of the entity to search for"
                    }
                }
            }
        ]
    }


# MCP Protocol endpoints (for compatibility)
@app.post("/mcp/tools/call")
async def mcp_tool_call(request: Dict[str, Any]):
    """
    MCP protocol endpoint for tool calls
    Handles requests in MCP format
    """
    try:
        tool_name = request.get("name")
        arguments = request.get("arguments", {})
        
        if tool_name == "get_entity_news":
            entity_name = arguments.get("entity_name")
            if not entity_name:
                raise HTTPException(status_code=400, detail="entity_name is required")
            
            result = await _get_entity_news_async(entity_name)
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }
                ]
            }
        else:
            raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# MCP Protocol JSON-RPC 2.0 Handler
@app.post("/mcp")
@app.get("/mcp")  # Some clients might try GET first
async def mcp_jsonrpc(request: Request):
    """
    Main MCP protocol endpoint using JSON-RPC 2.0
    Handles all MCP protocol requests
    """
    # Handle GET requests
    if request.method == "GET":
        return {
            "jsonrpc": "2.0",
            "result": {
                "protocol": "mcp",
                "version": "0.1.0",
                "server": "Entity News MCP Server",
                "endpoints": {
                    "mcp": "/mcp",
                    "sse": "/sse"
                }
            },
            "id": None
        }
    
    try:
        # Parse JSON body
        body = await request.json()
        logger.info(f"MCP request received: method={body.get('method')}, id={body.get('id')}")
        
        # Extract JSON-RPC fields
        jsonrpc = body.get("jsonrpc", "2.0")
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        
        if jsonrpc != "2.0":
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32600,
                    "message": "Invalid Request",
                    "data": "jsonrpc must be '2.0'"
                },
                "id": request_id
            }
        
        # Handle different MCP methods
        if method == "tools/list" or method == "tools/list_tools":
            result = _get_mcp_tool_list()
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name == "get_entity_news":
                entity_name = arguments.get("entity_name")
                if not entity_name:
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32602,
                            "message": "Invalid params",
                            "data": "entity_name is required"
                        },
                        "id": request_id
                    }
                
                try:
                    result = await _get_entity_news_async(entity_name)
                    
                    return {
                        "jsonrpc": "2.0",
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, indent=2)
                                }
                            ]
                        },
                        "id": request_id
                    }
                except Exception as e:
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32000,
                            "message": "Server error",
                            "data": str(e)
                        },
                        "id": request_id
                    }
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": "Method not found",
                        "data": f"Tool {tool_name} not found"
                    },
                    "id": request_id
                }
        
        elif method == "initialize":
            # MCP initialization
            return {
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "Entity News MCP Server",
                        "version": "0.1.0"
                    }
                },
                "id": request_id
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": "Method not found",
                    "data": f"Unknown method: {method}"
                },
                "id": request_id
            }
    
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": "Internal error",
                "data": str(e)
            },
            "id": body.get("id") if isinstance(body, dict) else None
        }


# Legacy endpoint for backward compatibility
@app.get("/mcp/tools/list")
async def mcp_list_tools():
    """List tools in MCP format (legacy endpoint)"""
    return _get_mcp_tool_list()


# SSE endpoint for MCP protocol streaming
@app.get("/sse")
@app.post("/sse")  # Agent Builder sends POST to /sse
async def mcp_sse(request: Request):
    """
    Server-Sent Events endpoint for MCP protocol
    Provides streaming communication for MCP clients
    Handles both GET (SSE connection) and POST (JSON-RPC over SSE)
    """
    # If it's a POST request, handle it as JSON-RPC
    if request.method == "POST":
        try:
            body = await request.json()
            logger.info(f"SSE POST request received: {body}")
            
            # Handle JSON-RPC request
            jsonrpc = body.get("jsonrpc", "2.0")
            method = body.get("method")
            params = body.get("params", {})
            request_id = body.get("id")
            
            # Process the request using the same logic as /mcp endpoint
            if method == "tools/list" or method == "tools/list_tools":
                result = _get_mcp_tool_list()
                return {
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id
                }
            
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if tool_name == "get_entity_news":
                    entity_name = arguments.get("entity_name")
                    if not entity_name:
                        return {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32602,
                                "message": "Invalid params",
                                "data": "entity_name is required"
                            },
                            "id": request_id
                        }
                    
                    try:
                        result = _get_entity_news(entity_name)
                        
                        return {
                            "jsonrpc": "2.0",
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(result, indent=2)
                                    }
                                ]
                            },
                            "id": request_id
                        }
                    except Exception as e:
                        return {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32000,
                                "message": "Server error",
                                "data": str(e)
                            },
                            "id": request_id
                        }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32601,
                            "message": "Method not found",
                            "data": f"Tool {tool_name} not found"
                        },
                        "id": request_id
                    }
            
            elif method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "Entity News MCP Server",
                            "version": "0.1.0"
                        }
                    },
                    "id": request_id
                }
            
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": "Method not found",
                        "data": f"Unknown method: {method}"
                    },
                    "id": request_id
                }
        
        except Exception as e:
            logger.error(f"Error handling SSE POST: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                },
                "id": None
            }
    
    # GET request - SSE stream
    async def event_stream():
        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connection', 'status': 'connected'})}\n\n"
        
        # Keep connection alive and handle incoming requests
        try:
            while True:
                # In a real implementation, you'd parse incoming requests from the client
                # For now, we'll just keep the connection alive
                await asyncio.sleep(30)
                yield f": keepalive\n\n"
        except asyncio.CancelledError:
            yield f"data: {json.dumps({'type': 'connection', 'status': 'disconnected'})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# Handle POST requests to root - might be MCP protocol
@app.post("/")
async def root_post(request: Request):
    """Handle POST requests to root - might be MCP protocol"""
    try:
        body = await request.json()
        # If it looks like a JSON-RPC request, forward to /mcp
        if "jsonrpc" in body and "method" in body:
            return await mcp_jsonrpc(request)
    except:
        pass
    
    # Otherwise return server info
    return {
        "status": "ok",
        "service": "Entity News MCP Server",
        "version": "0.1.0",
        "protocol": "mcp",
        "endpoints": {
            "mcp": "/mcp",
            "sse": "/sse",
            "health": "/health"
        },
        "tools": ["get_entity_news"]
    }


# Alternative MCP endpoint paths (some clients might use these)
@app.post("/mcp/v1")
async def mcp_jsonrpc_v1(request: Request):
    """Alternative MCP endpoint path"""
    return await mcp_jsonrpc(request)


if __name__ == "__main__":
    # Run the server with increased timeouts
    uvicorn.run(
        "http_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        timeout_keep_alive=300,  # Keep connections alive for 5 minutes
        timeout_graceful_shutdown=30,  # Graceful shutdown timeout
        limit_concurrency=100,  # Max concurrent connections
        limit_max_requests=1000,  # Max requests before restart
    )

