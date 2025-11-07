"""
FastMCP Server for Entity News.
"""

import pprint
from mcp.server.fastmcp import FastMCP
from utils import get_entity_news_from_api, get_entity_news_from_gnews
from typing import List

mcp = FastMCP("Entity News")


# Add a tool to get news articles for an entity
@mcp.tool()
def get_entity_news(entity_name: str) -> List[dict]:
    """Get news articles for an entity"""
    list1 = get_entity_news_from_api(entity_name)
    list2 = get_entity_news_from_gnews(entity_name)
    return list1 + list2

n = get_entity_news("google")

pprint.pprint(n[0])