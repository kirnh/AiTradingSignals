"""
HTTP Wrapper for MCP Server
Exposes MCP tools via HTTP/HTTPS for OpenAI Agent Builder
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
from utils import get_entity_news_from_api, get_entity_news_from_gnews

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
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Entity News MCP Server",
        "version": "0.1.0",
        "tools": ["get_entity_news"]
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/tools/get_entity_news", response_model=ToolResponse)
async def get_entity_news_tool(request: ToolRequest):
    """
    Get news articles for an entity
    
    This endpoint wraps the MCP tool and exposes it via HTTP
    """
    try:
        # Call the underlying functions
        list1 = get_entity_news_from_api(request.entity_name)
        list2 = get_entity_news_from_gnews(request.entity_name)
        result = list1 + list2
        
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
            
            list1 = get_entity_news_from_api(entity_name)
            list2 = get_entity_news_from_gnews(entity_name)
            result = list1 + list2
            
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


@app.get("/mcp/tools/list")
async def mcp_list_tools():
    """List tools in MCP format"""
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


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "http_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

