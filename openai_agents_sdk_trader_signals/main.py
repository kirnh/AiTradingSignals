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
from schemas import EntityEnrichmentOutput, NewsAggregationOutput, SentimentAnalysisOutput, RelatedEntity

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

    # Add self company entity to the output
    try:
        enrichment_data.entities.append(RelatedEntity(entity_name=company_name, relationship_strength=1.0, relationship_type="self"))
    except Exception as e:
        logger.error(f"Failed to add self company entity to output: {e}", exc_info=True)
        print(f"⚠️  Warning: Failed to add self company entity to output: {e}")
        raise
    
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
    # Process entities in batches to avoid token limits, with parallel processing for speed
    logger.info("-"*60)
    logger.info("STEP 3: Sentiment Analysis - Starting...")
    logger.debug(f"Agent: {sentiment_analysis_agent.name}")
    logger.debug(f"Agent tools: {[t.name for t in sentiment_analysis_agent.tools]}")
    logger.debug(f"Analyzing {total_articles} articles across {len(news_data.entities)} entities")
    
    print("\n" + "-"*60)
    print("Step 3: Sentiment Analysis - Analyzing sentiment signals...")
    print(f"Processing {len(news_data.entities)} entities in parallel batches...")
    
    # Process entities in batches of 2 to avoid token limits
    BATCH_SIZE = 2
    MAX_CONCURRENT_BATCHES = 3  # Process up to 3 batches in parallel to avoid rate limits
    total_entities = len(news_data.entities)
    total_batches = (total_entities + BATCH_SIZE - 1) // BATCH_SIZE
    
    async def process_batch(batch_num: int, batch_entities: list, batch_start: int, batch_end: int):
        """Process a single batch of entities and return the sentiment data."""
        logger.info(f"Processing batch {batch_num}/{total_batches}: entities {batch_start+1}-{batch_end} of {total_entities}")
        print(f"  Batch {batch_num}/{total_batches}: Processing {len(batch_entities)} entities...")
        
        # Create a batch input with just these entities
        batch_input = NewsAggregationOutput(
            company_name=news_data.company_name,
            entities=batch_entities
        )
        
        try:
            sentiment_result = await runner.run(
                sentiment_analysis_agent,
                input=batch_input.model_dump_json()
            )
            logger.debug(f"Batch {batch_num} sentiment analysis completed")
            
            # Get the structured output for this batch
            batch_sentiment_data = sentiment_result.final_output_as(SentimentAnalysisOutput)
            
            batch_articles = sum(len(e.news) for e in batch_sentiment_data.entities)
            batch_tokens = sum(
                len(article.sentiment_tokens)
                for entity in batch_sentiment_data.entities
                for article in entity.news
            )
            logger.info(f"✓ Batch {batch_num}: Processed {batch_articles} articles, generated {batch_tokens} tokens")
            print(f"    ✓ Batch {batch_num}: {batch_articles} articles, {batch_tokens} tokens")
            
            return batch_sentiment_data.entities, batch_num
            
        except Exception as e:
            logger.error(f"Failed to process batch {batch_num}: {e}", exc_info=True)
            logger.error(f"Batch entities: {[e.entity_name for e in batch_entities]}")
            print(f"  ⚠️  ERROR in batch {batch_num}: {e}")
            return None, batch_num
    
    # Create all batch tasks
    batch_tasks = []
    for batch_start in range(0, total_entities, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_entities)
        batch_entities = news_data.entities[batch_start:batch_end]
        batch_num = (batch_start // BATCH_SIZE) + 1
        
        batch_tasks.append(
            process_batch(batch_num, batch_entities, batch_start, batch_end)
        )
    
    # Process batches in parallel with concurrency limit
    all_sentiment_entities_dict = {}  # Use dict to deduplicate and maintain order
    completed_batches = set()
    
    # Process batches in chunks to respect concurrency limit
    for i in range(0, len(batch_tasks), MAX_CONCURRENT_BATCHES):
        chunk = batch_tasks[i:i + MAX_CONCURRENT_BATCHES]
        chunk_batch_nums = [j + 1 for j in range(i, min(i + MAX_CONCURRENT_BATCHES, len(batch_tasks)))]
        logger.info(f"Processing batches {chunk_batch_nums} in parallel...")
        
        results = await asyncio.gather(*chunk, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch task failed with exception: {result}", exc_info=True)
                continue
            
            entities, batch_num = result
            if entities is not None:
                # Store entities by name to maintain order and avoid duplicates
                for entity in entities:
                    all_sentiment_entities_dict[entity.entity_name] = entity
                completed_batches.add(batch_num)
    
    # Maintain original entity order from input
    ordered_entities = []
    for entity in news_data.entities:
        if entity.entity_name in all_sentiment_entities_dict:
            ordered_entities.append(all_sentiment_entities_dict[entity.entity_name])
    
    sentiment_data = SentimentAnalysisOutput(
        company_name=news_data.company_name,
        entities=ordered_entities
    )
    
    logger.info(f"✓ Completed sentiment analysis for {len(completed_batches)}/{total_batches} batches")
    print(f"✓ Completed {len(completed_batches)}/{total_batches} batches")
    
    # Validate that all entities and articles were processed
    input_entity_count = len(news_data.entities)
    output_entity_count = len(sentiment_data.entities)
    
    print(f"\n📊 Step 3 Validation:")
    print(f"  Input entities: {input_entity_count}")
    print(f"  Output entities: {output_entity_count}")
    
    if input_entity_count != output_entity_count:
        missing_entities = set(e.entity_name for e in news_data.entities) - set(e.entity_name for e in sentiment_data.entities)
        logger.error(f"🚨 CRITICAL: Step 3 processed {output_entity_count} entities, but input had {input_entity_count} entities!")
        logger.error(f"Missing entities: {missing_entities}")
        print(f"  ⚠️  WARNING: Only processed {output_entity_count}/{input_entity_count} entities!")
        print(f"  Missing: {', '.join(missing_entities)}")
    else:
        print(f"  ✓ All {input_entity_count} entities processed")
    
    # Check article counts per entity
    total_input_articles = 0
    total_output_articles = 0
    missing_articles = []
    
    for input_entity in news_data.entities:
        output_entity = next((e for e in sentiment_data.entities if e.entity_name == input_entity.entity_name), None)
        input_article_count = len(input_entity.news)
        total_input_articles += input_article_count
        
        if output_entity:
            output_article_count = len(output_entity.news)
            total_output_articles += output_article_count
            if input_article_count != output_article_count:
                missing_count = input_article_count - output_article_count
                logger.warning(f"⚠️ Entity '{input_entity.entity_name}': Processed {output_article_count}/{input_article_count} articles")
                missing_articles.append(f"{input_entity.entity_name}: {missing_count} missing")
        else:
            logger.error(f"🚨 Entity '{input_entity.entity_name}' is MISSING from Step 3 output!")
            missing_articles.append(f"{input_entity.entity_name}: ALL articles missing")
    
    print(f"  Input articles: {total_input_articles}")
    print(f"  Output articles: {total_output_articles}")
    
    if total_input_articles != total_output_articles:
        print(f"  ⚠️  WARNING: Only processed {total_output_articles}/{total_input_articles} articles!")
        if missing_articles:
            print(f"  Missing articles in: {', '.join(missing_articles[:5])}")
            if len(missing_articles) > 5:
                print(f"  ... and {len(missing_articles) - 5} more entities with missing articles")
    else:
        print(f"  ✓ All {total_input_articles} articles processed")
    
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
