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
from utils import get_entity_news_from_api, get_entity_news_from_gnews

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_entity_news(entity_name: str) -> List[Dict[str, Any]]:
    """Helper function to fetch news from all sources."""
    list1 = get_entity_news_from_api(entity_name)
    list2 = get_entity_news_from_gnews(entity_name)
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
        result = _get_entity_news(request.entity_name)
        return ToolResponse(
            success=True,
            data=result
        )
    except Exception as e:
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
            
            result = _get_entity_news(entity_name)
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": str(result)
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
    # Run the server
    uvicorn.run(
        "http_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

