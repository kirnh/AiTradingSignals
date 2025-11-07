import os
import json
import asyncio
import logging
from agents import Agent, Runner
from tools import get_entity_news, fetch_article_content
from prompts import (
    entity_enrichment_agent_config,
    news_aggregation_agent_config,
    sentiment_analysis_agent_config
)
from schemas import EntityEnrichmentOutput, NewsAggregationOutput, SentimentAnalysisOutput

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
    
    print(f"✓ Found {len(enrichment_data.entities)} related entities")
    for entity in enrichment_data.entities[:3]:
        logger.debug(f"Entity: {entity.entity_name} - {entity.relationship_type} (strength: {entity.relationship_strength})")
        print(f"  - {entity.entity_name} ({entity.relationship_type}, strength: {entity.relationship_strength})")
    if len(enrichment_data.entities) > 3:
        logger.debug(f"... and {len(enrichment_data.entities) - 3} more entities")
        print(f"  ... and {len(enrichment_data.entities) - 3} more")
    
    # Step 2: News Aggregation (returns NewsAggregationOutput)
    logger.info("-"*60)
    logger.info("STEP 2: News Aggregation - Starting...")
    logger.debug(f"Agent: {news_aggregation_agent.name}")
    logger.debug(f"Agent tools: {[t.name for t in news_aggregation_agent.tools]}")
    logger.debug(f"Processing {len(enrichment_data.entities)} entities")
    
    print("\n" + "-"*60)
    print("Step 2: News Aggregation - Fetching news for entities...")
    
    news_result = await runner.run(
        news_aggregation_agent,
        input=enrichment_data.model_dump_json()
    )
    logger.debug("News aggregation agent completed")
    
    # Get the structured output
    news_data = news_result.final_output_as(NewsAggregationOutput)
    total_articles = sum(len(entity.news) for entity in news_data.entities)
    logger.info(f"✓ Aggregated {total_articles} news articles across {len(news_data.entities)} entities")
    
    for entity in news_data.entities:
        logger.debug(f"Entity '{entity.entity_name}': {len(entity.news)} articles found")
    
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
    total_tokens = sum(len(entity.sentiment_tokens) for entity in sentiment_data.entities)
    logger.info(f"✓ Generated {total_tokens} sentiment tokens")
    
    print(f"✓ Generated {total_tokens} sentiment tokens")
    
    # Show sample sentiment tokens
    logger.debug("Sample sentiment tokens:")
    for entity in sentiment_data.entities[:2]:
        if entity.sentiment_tokens:
            print(f"\n  {entity.entity_name}:")
            logger.debug(f"Entity: {entity.entity_name} - {len(entity.sentiment_tokens)} tokens")
            for token in entity.sentiment_tokens[:2]:
                print(f"    • {token.token_text}")
                print(f"      Impact: {token.impact}, Direction: {token.direction}, Strength: {token.strength}")
                logger.debug(f"  Token: {token.token_text} | {token.impact}/{token.direction} ({token.strength})")
    
    print(f"\n{'='*60}")
    print("Pipeline Complete!")
    print(f"{'='*60}\n")
    
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
    
    # Save results (result is now a validated SentimentAnalysisOutput object)
    output_file = f"trading_signals_{company.lower().replace(' ', '_')}.json"
    logger.info(f"Saving results to: {output_file}")
    
    with open(output_file, 'w') as f:
        # Use model_dump() to convert Pydantic model to dict
        json.dump(result.model_dump(), f, indent=2)
    
    logger.info(f"✓ Results saved successfully")
    logger.info(f"Total entities analyzed: {len(result.entities)}")
    
    total_tokens = sum(len(e.sentiment_tokens) for e in result.entities)
    logger.info(f"Total sentiment signals: {total_tokens}")
    
    print(f"\n✓ Results saved to: {output_file}")
    print(f"  Total entities analyzed: {len(result.entities)}")
    print(f"  Total sentiment signals: {total_tokens}")
    
    logger.info("="*80)
    logger.info("APPLICATION END")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
