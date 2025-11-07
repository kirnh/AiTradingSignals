import os
import json
import asyncio
import logging
from dotenv import load_dotenv
from agents import Agent, Runner
from tools import get_entity_news, fetch_article_content, get_tool_call_count, reset_tool_call_counter
from prompts import (
    entity_enrichment_agent_config,
    news_aggregation_agent_config,
    sentiment_analysis_agent_config
)
from schemas import EntityEnrichmentOutput, NewsAggregationOutput, SentimentAnalysisOutput

# Load environment variables from .env file
load_dotenv()

# Configure verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Create the three agents with their respective tools and structured outputs
# Note: Entity Enrichment Agent uses web browsing instead of custom tools
entity_enrichment_agent = Agent(
    name="Entity Enrichment Agent",
    instructions=entity_enrichment_agent_config["instructions"],
    tools=[],  # Uses built-in web browsing capability
    model="gpt-4o",
    output_type=entity_enrichment_agent_config["output_type"]
)

news_aggregation_agent = Agent(
    name="News Aggregation Agent", 
    instructions=news_aggregation_agent_config["instructions"],
    tools=[get_entity_news],
    model="gpt-4o",
    output_type=news_aggregation_agent_config["output_type"]
)

sentiment_analysis_agent = Agent(
    name="Sentiment Analysis Agent",
    instructions=sentiment_analysis_agent_config["instructions"],
    tools=[fetch_article_content],
    model="gpt-4o",
    output_type=sentiment_analysis_agent_config["output_type"]
)


async def run_trading_signal_pipeline(company_name: str):
    """
    Run the complete trading signals pipeline for a company.
    
    Args:
        company_name: Name of the company to analyze
        
    Returns:
        SentimentAnalysisOutput: Validated structured output with all analysis
    """
    # Reset tool call counters at the start
    reset_tool_call_counter()
    
    logger.info("="*60)
    logger.info(f"PIPELINE START: Trading Signal Analysis for {company_name}")
    logger.info("="*60)
    
    print(f"\n{'='*60}")
    print(f"Starting Trading Signal Analysis for: {company_name}")
    print(f"{'='*60}\n")
    
    # Step 1: Entity Enrichment (returns EntityEnrichmentOutput)
    logger.info("STEP 1: Entity Enrichment - Starting...")
    logger.debug(f"Input: {json.dumps({'company_name': company_name})}")
    print("Step 1: Entity Enrichment - Finding related entities...")
    
    runner = Runner()
    logger.debug("Runner initialized")
    logger.debug(f"Agent: {entity_enrichment_agent.name}")
    logger.debug(f"Agent tools: {[t.name for t in entity_enrichment_agent.tools]}")
    
    enrichment_result = await runner.run(
        entity_enrichment_agent,
        input=json.dumps({"company_name": company_name})
    )
    logger.debug("Entity enrichment agent completed")
    
    # Get the structured output (automatically parsed and validated!)
    enrichment_data = enrichment_result.final_output_as(EntityEnrichmentOutput)
    logger.info(f"✓ Found {len(enrichment_data.entities)} related entities")
    
    # Save Step 1 output
    step1_file = f"step1_entity_enrichment_{company_name.lower().replace(' ', '_')}.json"
    with open(step1_file, 'w') as f:
        json.dump(enrichment_data.model_dump(), f, indent=2)
    logger.info(f"✓ Saved Step 1 output to: {step1_file}")
    
    print(f"✓ Found {len(enrichment_data.entities)} related entities")
    for entity in enrichment_data.entities:
        logger.debug(f"Entity: {entity.entity_name} - {entity.relationship_type} (strength: {entity.relationship_strength})")
        print(f"  - {entity.entity_name} ({entity.relationship_type}, strength: {entity.relationship_strength})")
    
    # Log all entities
    logger.info(f"All entities: {[e.entity_name for e in enrichment_data.entities]}")
    
    # Step 2: News Aggregation (returns NewsAggregationOutput)
    logger.info("-"*60)
    logger.info("STEP 2: News Aggregation - Starting...")
    logger.debug(f"Agent: {news_aggregation_agent.name}")
    logger.debug(f"Agent tools: {[t.name for t in news_aggregation_agent.tools]}")
    logger.debug(f"Processing {len(enrichment_data.entities)} entities")
    
    # Log all entity names that should get news
    entity_names = [e.entity_name for e in enrichment_data.entities]
    logger.info(f"Entities to fetch news for: {entity_names}")
    logger.info(f"⚠️  CRITICAL: Agent MUST call get_entity_news() {len(entity_names)} times (once per entity)")
    
    print("\n" + "-"*60)
    print("Step 2: News Aggregation - Fetching news for entities...")
    print(f"  Entities: {', '.join(entity_names[:5])}{', ...' if len(entity_names) > 5 else ''}")
    print(f"  Expected: {len(entity_names)} tool calls")
    
    news_result = await runner.run(
        news_aggregation_agent,
        input=enrichment_data.model_dump_json()
    )
    logger.debug("News aggregation agent completed")
    
    # Get the structured output
    news_data = news_result.final_output_as(NewsAggregationOutput)
    total_articles = sum(len(entity.news) for entity in news_data.entities)
    logger.info(f"✓ Aggregated {total_articles} news articles across {len(news_data.entities)} entities")
    
    # Save Step 2 output
    step2_file = f"step2_news_aggregation_{company_name.lower().replace(' ', '_')}.json"
    try:
        with open(step2_file, 'w') as f:
            json.dump(news_data.model_dump(), f, indent=2)
        logger.info(f"✓ Saved Step 2 output to: {step2_file}")
        print(f"✓ Saved Step 2 output to: {step2_file}")
    except Exception as e:
        logger.error(f"Failed to save Step 2 output: {e}", exc_info=True)
        print(f"⚠️  Warning: Failed to save Step 2 output: {e}")
    
    for entity in news_data.entities:
        logger.debug(f"Entity '{entity.entity_name}': {len(entity.news)} articles found")
    
    # Check if all entities from step 1 are in step 2
    step1_entities = set(e.entity_name for e in enrichment_data.entities)
    step2_entities = set(e.entity_name for e in news_data.entities)
    missing_entities = step1_entities - step2_entities
    if missing_entities:
        logger.warning(f"⚠️ Missing entities in Step 2: {missing_entities}")
    
    # Check tool call count
    tool_calls = get_tool_call_count("get_entity_news")
    expected_calls = len(entity_names)
    logger.info(f"Tool call summary: get_entity_news called {tool_calls} times (expected: {expected_calls})")
    print(f"\n  Tool calls: {tool_calls} / {expected_calls} expected")
    
    if tool_calls < expected_calls:
        logger.error(f"🚨 CRITICAL: get_entity_news only called {tool_calls} times, expected {expected_calls}!")
        logger.error(f"The agent did not fetch news for all entities!")
        print(f"  ⚠️  WARNING: Only {tool_calls} tool calls made, expected {expected_calls}")
    
    # Check for entities with empty news (this indicates the tool wasn't called properly)
    entities_with_no_news = [e.entity_name for e in news_data.entities if len(e.news) == 0]
    if entities_with_no_news:
        logger.error(f"🚨 CRITICAL: {len(entities_with_no_news)} entities have NO news articles: {entities_with_no_news}")
        logger.error(f"This means get_entity_news was not called or returned empty results for these entities!")
        print(f"\n⚠️  WARNING: {len(entities_with_no_news)} entities have no news:")
        for name in entities_with_no_news[:5]:
            print(f"  - {name}")
        if len(entities_with_no_news) > 5:
            print(f"  ... and {len(entities_with_no_news) - 5} more")
    
    print(f"✓ Aggregated {total_articles} news articles across {len(news_data.entities)} entities")
    
    # Step 3: Sentiment Analysis (returns SentimentAnalysisOutput)
    logger.info("-"*60)
    logger.info("STEP 3: Sentiment Analysis - Starting...")
    logger.debug(f"Agent: {sentiment_analysis_agent.name}")
    logger.debug(f"Agent tools: {[t.name for t in sentiment_analysis_agent.tools]}")
    logger.debug(f"Analyzing {total_articles} articles across {len(news_data.entities)} entities")
    
    print("\n" + "-"*60)
    print("Step 3: Sentiment Analysis - Analyzing sentiment signals...")
    
    sentiment_result = await runner.run(
        sentiment_analysis_agent,
        input=news_data.model_dump_json()
    )
    logger.debug("Sentiment analysis agent completed")
    
    # Get the structured output
    sentiment_data = sentiment_result.final_output_as(SentimentAnalysisOutput)
    # Count tokens across all articles in all entities
    total_tokens = sum(
        len(article.sentiment_tokens)
        for entity in sentiment_data.entities
        for article in entity.news
    )
    logger.info(f"✓ Generated {total_tokens} sentiment tokens across all articles")
    
    # Save Step 3 output
    step3_file = f"step3_sentiment_analysis_{company_name.lower().replace(' ', '_')}.json"
    with open(step3_file, 'w') as f:
        json.dump(sentiment_data.model_dump(), f, indent=2)
    logger.info(f"✓ Saved Step 3 output to: {step3_file}")
    
    # Check if all entities from step 2 are in step 3
    step3_entities = set(e.entity_name for e in sentiment_data.entities)
    missing_entities_step3 = step2_entities - step3_entities
    if missing_entities_step3:
        logger.warning(f"⚠️ Missing entities in Step 3: {missing_entities_step3}")
    
    # Log token distribution per entity and article
    for entity in sentiment_data.entities:
        entity_token_count = sum(len(article.sentiment_tokens) for article in entity.news)
        logger.debug(f"Entity '{entity.entity_name}': {entity_token_count} sentiment tokens across {len(entity.news)} articles")
        for article in entity.news:
            if article.sentiment_tokens:
                logger.debug(f"  Article '{article.title[:50]}...': {len(article.sentiment_tokens)} tokens")
    
    print(f"✓ Generated {total_tokens} sentiment tokens across all articles")
    
    # Show sample sentiment tokens
    logger.debug("Sample sentiment tokens:")
    shown_count = 0
    for entity in sentiment_data.entities:
        if shown_count >= 2:
            break
        for article in entity.news:
            if article.sentiment_tokens and shown_count < 2:
                print(f"\n  {entity.entity_name} - {article.title[:60]}...")
                logger.debug(f"Entity: {entity.entity_name}, Article: {article.title[:50]}... - {len(article.sentiment_tokens)} tokens")
                for token in article.sentiment_tokens[:2]:
                    print(f"    • {token.token_text}")
                    print(f"      Impact: {token.impact}, Direction: {token.direction}, Strength: {token.strength}")
                    logger.debug(f"  Token: {token.token_text} | {token.impact}/{token.direction} ({token.strength})")
                shown_count += 1
                if shown_count >= 2:
                    break
    
    print(f"\n{'='*60}")
    print("Pipeline Complete!")
    print(f"{'='*60}\n")
    
    # Pipeline Summary
    logger.info("="*60)
    logger.info("PIPELINE SUMMARY")
    logger.info("="*60)
    logger.info(f"Step 1 - Entity Enrichment: {len(enrichment_data.entities)} entities found")
    logger.info(f"Step 2 - News Aggregation: {len(news_data.entities)} entities with news")
    logger.info(f"Step 3 - Sentiment Analysis: {len(sentiment_data.entities)} entities with sentiment")
    
    if len(enrichment_data.entities) != len(news_data.entities):
        logger.warning(f"⚠️ Entity count mismatch: Step 1 ({len(enrichment_data.entities)}) vs Step 2 ({len(news_data.entities)})")
    if len(news_data.entities) != len(sentiment_data.entities):
        logger.warning(f"⚠️ Entity count mismatch: Step 2 ({len(news_data.entities)}) vs Step 3 ({len(sentiment_data.entities)})")
    
    logger.info(f"Total news articles: {total_articles}")
    logger.info(f"Total sentiment tokens: {total_tokens} (across all articles)")
    
    # Print intermediate files saved
    logger.info("Intermediate outputs saved:")
    logger.info(f"  - {step1_file}")
    logger.info(f"  - {step2_file}")
    logger.info(f"  - {step3_file}")
    
    logger.info("="*60)
    logger.info("PIPELINE COMPLETE")
    logger.info("="*60)
    
    return sentiment_data


async def main():
    """Main entry point for the trading signals application."""
    
    logger.info("="*80)
    logger.info("APPLICATION START: AI Trading Signals - Multi-Agent Pipeline")
    logger.info("="*80)
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        print("Please set it with: export OPENAI_API_KEY='your-api-key'")
        return
    
    logger.info("✓ OPENAI_API_KEY found")
    
    # Check for news API configuration
    news_api_provider = os.getenv("NEWS_API_PROVIDER", "gnews").lower()
    logger.info(f"News API Provider: {news_api_provider}")
    
    if news_api_provider == "gnews":
        if not os.getenv("GNEWS_API_KEY"):
            logger.warning("GNEWS_API_KEY not set, using default key")
        else:
            logger.info("✓ GNEWS_API_KEY found")
    elif news_api_provider == "newsapi":
        if not os.getenv("NEWSAPI_KEY"):
            logger.warning("NEWSAPI_KEY not set, using default key")
        else:
            logger.info("✓ NEWSAPI_KEY found")
    else:
        logger.warning(f"Unknown NEWS_API_PROVIDER '{news_api_provider}', defaulting to 'gnews'")
    
    # Example usage
    companies = ["Apple", "Microsoft", "Tesla"]
    logger.info(f"Available companies: {companies}")
    
    print("AI Trading Signals - Multi-Agent Pipeline")
    print("Agents:")
    print("  1. Entity Enrichment Agent - Finds related entities (uses web browsing)")
    print("  2. News Aggregation Agent - Fetches news articles")
    print("  3. Sentiment Analysis Agent - Analyzes sentiment signals")
    print()
    
    # Run for first company as example
    company = companies[0]
    logger.info(f"Selected company: {company}")
    
    result = await run_trading_signal_pipeline(company)
    
    logger.info(f"Total entities analyzed: {len(result.entities)}")
    
    total_tokens = sum(
        len(article.sentiment_tokens)
        for entity in result.entities
        for article in entity.news
    )
    logger.info(f"Total sentiment signals: {total_tokens} (across all articles)")
    
    print(f"  Total entities analyzed: {len(result.entities)}")
    print(f"  Total sentiment signals: {total_tokens} (across all articles)")
    
    logger.info("="*80)
    logger.info("APPLICATION END")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
