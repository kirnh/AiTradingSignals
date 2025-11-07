# AI Trading Signals - Multi-Agent System

A multi-agent system using OpenAI's Agents SDK to analyze trading signals by enriching company data, aggregating news, and performing sentiment analysis on related entities.

## Architecture

The system uses three specialized agents that work in a pipeline, with **structured outputs** using Pydantic schemas (similar to LangChain's approach) for guaranteed, validated responses:

### 1. Entity Enrichment Agent
- **Purpose**: Discovers entities related to a target company
- **Tools**: Uses built-in web browsing (no custom tools)
- **Output**: List of related entities (competitors, suppliers, executives, partners) with relationship strength and type

### 2. News Aggregation Agent
- **Purpose**: Fetches recent news for each related entity
- **Tools**: `get_entity_news`
- **Output**: News articles with URLs, publication dates, and sources

### 3. Sentiment Analysis Agent
- **Purpose**: Analyzes news sentiment and generates trading signals
- **Tools**: `fetch_article_content`
- **Output**: Sentiment tokens indicating impact, direction, and strength

## Structured Outputs with Pydantic

All agents use **Pydantic schemas** for structured outputs, ensuring type-safe, validated responses:

```python
import asyncio
from pydantic import BaseModel, Field
from typing import List
from agents import Agent, Runner

# Define output schema
class EntityEnrichmentOutput(BaseModel):
    company_name: str
    entities: List[RelatedEntity] = Field(min_length=1)

# Agent returns validated data matching this schema
agent = Agent(
    name="Entity Enrichment Agent",
    instructions="...",
    tools=[],
    model="gpt-4o",
    output_type=EntityEnrichmentOutput  # ← Pydantic schema
)

# Get validated output (runner.run() is async!)
async def run_agent():
    runner = Runner()
    result = await runner.run(agent, input='{"company_name": "Apple"}')
    
    # Get the structured output (automatically validated!)
    data = result.final_output_as(EntityEnrichmentOutput)
    
    # Type-safe access with IDE auto-completion
    print(data.company_name)  # "Apple"
    print(data.entities[0].entity_name)  # "TSMC"

asyncio.run(run_agent())
```

**Benefits:**
- ✅ Guaranteed format from LLM responses
- ✅ Automatic validation
- ✅ Type safety and IDE support
- ✅ Self-documenting schemas
- ✅ Fewer runtime errors

> 📖 **Important Notes**:
> - The parameter is `output_type`, not `response_format`
> - `Runner.run()` is **async** - always use `await` and `asyncio.run()`
> - Access output with `result.final_output_as(YourSchema)` - automatically validated!
> - Tools must use `@function_tool` decorator from `agents` package


## How Tools Connect to Agents

```python
from agents import Agent
from tools import get_entity_news, fetch_article_content
from prompts import entity_enrichment_agent_config
from schemas import EntityEnrichmentOutput, NewsAggregationOutput

# Create an agent with custom tools and structured output
news_agent = Agent(
    name="News Aggregation Agent",
    instructions="Fetch news for companies",
    tools=[get_entity_news],  # ← Custom tools
    model="gpt-4o",
    output_type=NewsAggregationOutput  # ← Pydantic schema
)

# Or use built-in capabilities like web browsing
enrichment_agent = Agent(
    name="Entity Enrichment Agent",
    instructions=entity_enrichment_agent_config["instructions"],
    tools=[],  # ← Built-in web browsing
    model="gpt-4o",
    output_type=EntityEnrichmentOutput  # ← Structured output
)
```

### Tool Requirements

Each tool must be a **Python function decorated with `@function_tool`** with:
1. **`@function_tool` decorator** from `agents` package
2. **Type hints** for parameters and return value
3. **Docstring** explaining what it does
4. **String return type** (for OpenAI Agents SDK)

Example:

```python
from agents import function_tool
import json

@function_tool  # ← Required decorator!
def get_entity_news(entity_name: str, num_results: int = 10) -> str:
    """
    Fetch news articles for an entity using GNews API.
    
    Args:
        entity_name: Name of the entity to fetch news for
        num_results: Number of articles to fetch (default: 10)
        
    Returns:
        JSON string containing news articles
    """
    # Implementation here
    return json.dumps(articles)
```

The `@function_tool` decorator:
- Wraps the function as a `FunctionTool` object
- Parses the function signature automatically
- Reads the docstring for tool description
- Makes it recognizable by the SDK
- Enables the LLM to call it properly

## Installation

1. Install dependencies:
```bash
uv sync
# or
pip install -e .
```

2. Set your OpenAI API key:
```bash
export OPENAI_API_KEY='your-api-key-here'
```

## Verbose Logging

The system includes **comprehensive verbose logging** to help you understand what's happening at every step:

```python
# Logging is automatically configured with DEBUG level
# Shows:
# - Agent initialization and execution
# - Tool calls and results
# - API requests and responses
# - Data processing steps
# - Errors with full stack traces
```

**Log levels:**
- `INFO` - Major steps and results
- `DEBUG` - Detailed execution flow, API calls, data processing
- `ERROR` - Errors with stack traces

**Example log output:**
```
2025-11-07 14:30:00 - main - INFO - PIPELINE START: Trading Signal Analysis for Apple
2025-11-07 14:30:00 - main - INFO - STEP 1: Entity Enrichment - Starting...
2025-11-07 14:30:00 - main - DEBUG - Agent: Entity Enrichment Agent
2025-11-07 14:30:05 - main - INFO - ✓ Found 5 related entities
2025-11-07 14:30:05 - tools - INFO - TOOL CALL: get_entity_news(entity_name='TSMC', num_results=10)
2025-11-07 14:30:06 - tools - DEBUG - API response status: 200
2025-11-07 14:30:06 - tools - INFO - ✓ Fetched 10 articles for 'TSMC'
```

All logs include **timestamps**, **module names**, and **log levels** for easy debugging.

## Usage

### Basic Usage

```python
import asyncio
from main import run_trading_signal_pipeline

# Analyze a company (async function)
async def analyze():
    result = await run_trading_signal_pipeline("Apple")
    return result

# Run it
result = asyncio.run(analyze())
```

### Run the Complete Pipeline

```bash
python main.py
```

This will:
1. Analyze the target company (default: Apple)
2. Find related entities
3. Fetch news for each entity
4. Perform sentiment analysis
5. Save results to a JSON file

### Using Individual Agents

```python
import json
import asyncio
from agents import Runner
from main import entity_enrichment_agent
from schemas import EntityEnrichmentOutput

async def use_single_agent():
    runner = Runner()
    
    # Use just the entity enrichment agent
    result = await runner.run(
        entity_enrichment_agent,
        input=json.dumps({"company_name": "Microsoft"})
    )
    
    # Get the structured output (automatically validated!)
    data = result.final_output_as(EntityEnrichmentOutput)
    print(f"Found {len(data.entities)} entities for {data.company_name}")

asyncio.run(use_single_agent())
```

## Project Structure

```
.
├── main.py           # Main pipeline and agent initialization
├── prompts.py        # Agent instructions and configurations
├── tools.py          # Tool functions for agents
├── schemas.py        # Pydantic schemas for structured outputs
├── pyproject.toml    # Dependencies
├── README.md         # This file (full documentation)
└── QUICK_START.md    # Quick reference guide with examples
```

## Tool-to-Agent Mapping

| Agent | Tools Used | Purpose |
|-------|-----------|---------|
| Entity Enrichment Agent | Web browsing (built-in) | Find competitors, suppliers, executives |
| News Aggregation Agent | `get_entity_news` | Fetch recent news articles |
| Sentiment Analysis Agent | `fetch_article_content` | Parse articles and extract sentiment |

## Data Flow

```
Input: Company Name
    ↓
[Entity Enrichment Agent]
    ↓ (uses web browsing to find real-time data)
Related Entities + Relationships
    ↓
[News Aggregation Agent]
    ↓ (uses get_entity_news)
Entities + News Articles
    ↓
[Sentiment Analysis Agent]
    ↓ (uses fetch_article_content)
Sentiment Tokens + Trading Signals
    ↓
Output: JSON with actionable insights
```

## Extending the System

### Adding a New Tool

1. **Create the tool function in `tools.py`:**

```python
from agents import function_tool
import json

@function_tool  # ← Don't forget the decorator!
def get_stock_price(ticker: str) -> str:
    """
    Fetch current stock price for a ticker.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        JSON string with price data
    """
    # Implementation
    return json.dumps({"ticker": ticker, "price": 150.25})
```

2. **Add it to an agent in `main.py`:**

```python
entity_enrichment_agent = Agent(
    name="Entity Enrichment Agent",
    instructions=entity_enrichment_agent_config["instructions"],
    tools=[search_related_entities, get_stock_price],  # Add here
    model="gpt-4o"
)
```

3. **Update the agent instructions in `prompts.py`** to mention the new tool.

### Creating a New Agent

1. **Add configuration to `prompts.py`:**

```python
risk_assessment_agent_config = {
    "instructions": """Analyze risk factors...""",
    "input_format": {...},
    "output_format": {...}
}
```

2. **Create the agent in `main.py`:**

```python
risk_assessment_agent = Agent(
    name="Risk Assessment Agent",
    instructions=risk_assessment_agent_config["instructions"],
    tools=[your_tools_here],
    model="gpt-4o"
)
```

3. **Integrate into the pipeline.**

## API Keys

The system uses two external APIs:

- **OpenAI API**: Required for agent operations (set `OPENAI_API_KEY`)
- **GNews API**: Used for news fetching (key included, but get your own at https://gnews.io)

## Notes

- The Entity Enrichment Agent uses the model's built-in web browsing to find real-time data about competitors, suppliers, executives, and partners
- Rate limiting and error handling should be enhanced for production use
- Consider adding caching for news and entity lookups
- Sentiment analysis can be improved with fine-tuned models
- For more structured entity data, consider integrating with:
  - Crunchbase API
  - LinkedIn API
  - Financial data providers (Bloomberg, FactSet)
  - SEC EDGAR for filings

## Example Output

```json
{
  "company_name": "Apple",
  "entities": [
    {
      "entity_name": "TSMC",
      "relationship_strength": 0.95,
      "relationship_type": "supplier",
      "news": [...],
      "sentiment_tokens": [
        {
          "tokenText": "TSMC expands production capacity",
          "impact": "positive",
          "direction": "bullish",
          "strength": 0.75
        }
      ]
    }
  ]
}
```

## License

MIT

