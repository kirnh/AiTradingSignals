"""
Pydantic schemas for structured outputs from agents.
Similar to LangChain's structured output approach.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List


# Entity Enrichment Agent Output Schema
class RelatedEntity(BaseModel):
    """A single related entity with relationship information."""
    entity_name: str = Field(description="Name of the related entity (company, person, or organization)")
    relationship_strength: float = Field(
        description="Strength of relationship from 0.0 to 1.0",
        ge=0.0,
        le=1.0
    )
    relationship_type: str = Field(
        description="Type of relationship: 'competitor', 'supplier', 'executive', 'partner', 'investor', 'customer'"
    )


class EntityEnrichmentOutput(BaseModel):
    """Output schema for Entity Enrichment Agent."""
    company_name: str = Field(description="The company being analyzed")
    entities: List[RelatedEntity] = Field(
        description="List of related entities with relationship information",
        min_length=1
    )


# News Aggregation Agent Output Schema
class NewsArticle(BaseModel):
    """A single news article."""
    url: str = Field(description="URL of the news article")
    published_date: str = Field(description="Publication date in ISO format")
    source: str = Field(description="Source of the news (e.g., 'Reuters', 'Bloomberg')")
    title: str = Field(description="Title of the article", default="")


class EntityWithNews(BaseModel):
    """An entity with its associated news articles."""
    entity_name: str = Field(description="Name of the entity")
    relationship_strength: float = Field(ge=0.0, le=1.0)
    relationship_type: str
    news: List[NewsArticle] = Field(description="List of news articles about this entity")


class NewsAggregationOutput(BaseModel):
    """Output schema for News Aggregation Agent."""
    company_name: str = Field(description="The company being analyzed")
    entities: List[EntityWithNews] = Field(
        description="List of entities with their news articles"
    )


# Sentiment Analysis Agent Output Schema
class SentimentToken(BaseModel):
    """A sentiment signal extracted from news."""
    model_config = ConfigDict(populate_by_name=True)  # Allow both token_text and tokenText
    
    token_text: str = Field(
        description="The key phrase or event from the news",
        alias="tokenText"
    )
    impact: str = Field(
        description="Impact on the main company: 'positive', 'negative', or 'neutral'"
    )
    direction: str = Field(
        description="Trading signal direction: 'bullish', 'bearish', or 'neutral'"
    )
    strength: float = Field(
        description="Strength of the signal from 0.0 to 1.0",
        ge=0.0,
        le=1.0
    )


class EntityWithSentiment(BaseModel):
    """An entity with news and sentiment analysis."""
    entity_name: str
    relationship_strength: float = Field(ge=0.0, le=1.0)
    relationship_type: str
    news: List[NewsArticle]
    sentiment_tokens: List[SentimentToken] = Field(
        description="List of sentiment signals extracted from news"
    )


class SentimentAnalysisOutput(BaseModel):
    """Output schema for Sentiment Analysis Agent."""
    company_name: str = Field(description="The company being analyzed")
    entities: List[EntityWithSentiment] = Field(
        description="List of entities with news and sentiment analysis"
    )


# Example usage and validation
if __name__ == "__main__":
    # Test the schemas
    import json
    
    # Test EntityEnrichmentOutput
    enrichment_data = {
        "company_name": "Apple",
        "entities": [
            {
                "entity_name": "TSMC",
                "relationship_strength": 0.95,
                "relationship_type": "supplier"
            },
            {
                "entity_name": "Samsung",
                "relationship_strength": 0.85,
                "relationship_type": "competitor"
            }
        ]
    }
    
    enrichment_output = EntityEnrichmentOutput(**enrichment_data)
    print("✓ EntityEnrichmentOutput validated")
    print(json.dumps(enrichment_output.model_dump(), indent=2))
    
    # Test NewsAggregationOutput
    news_data = {
        "company_name": "Apple",
        "entities": [
            {
                "entity_name": "TSMC",
                "relationship_strength": 0.95,
                "relationship_type": "supplier",
                "news": [
                    {
                        "url": "https://example.com/article",
                        "published_date": "2024-11-07",
                        "source": "Reuters",
                        "title": "TSMC expands capacity"
                    }
                ]
            }
        ]
    }
    
    news_output = NewsAggregationOutput(**news_data)
    print("\n✓ NewsAggregationOutput validated")
    print(json.dumps(news_output.model_dump(), indent=2))
    
    # Test SentimentAnalysisOutput
    sentiment_data = {
        "company_name": "Apple",
        "entities": [
            {
                "entity_name": "TSMC",
                "relationship_strength": 0.95,
                "relationship_type": "supplier",
                "news": [
                    {
                        "url": "https://example.com/article",
                        "published_date": "2024-11-07",
                        "source": "Reuters",
                        "title": "TSMC expands"
                    }
                ],
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
    
    sentiment_output = SentimentAnalysisOutput(**sentiment_data)
    print("\n✓ SentimentAnalysisOutput validated")
    print(json.dumps(sentiment_output.model_dump(), indent=2))
    
    print("\n✅ All schemas validated successfully!")

