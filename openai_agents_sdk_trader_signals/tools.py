import requests
from bs4 import BeautifulSoup
from agents import function_tool
import json
import logging

# Configure logger for tools
logger = logging.getLogger(__name__)



@function_tool
def get_entity_news(entity_name: str, num_results: int = 10) -> str:
    """
    Fetch news articles for an entity using GNews API.
    
    Args:
        entity_name: Name of the entity to fetch news for
        num_results: Number of articles to fetch (default: 10)
        
    Returns:
        JSON string containing news articles with url, published_date, source, title, description
    """
    logger.info(f"TOOL CALL: get_entity_news(entity_name='{entity_name}', num_results={num_results})")
    
    url = "https://gnews.io/api/v4/search"
    
    params = {
        'q': entity_name,
        'lang': 'en',
        'max': num_results,
        'apikey': 'db2651be6ce35c4956fbe1fc2a5a8cdb'
    }
    
    logger.debug(f"Calling GNews API: {url}")
    logger.debug(f"Query params: q={entity_name}, lang=en, max={num_results}")
    
    try:
        response = requests.get(url, params=params, timeout=10)
        logger.debug(f"API response status: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        
        articles = data.get('articles', [])
        logger.info(f"✓ Fetched {len(articles)} articles for '{entity_name}'")
        
        # Format to match expected output
        formatted_articles = []
        for article in articles:
            formatted_articles.append({
                'url': article.get('url'),
                'published_date': article.get('publishedAt'),
                'source': article.get('source', {}).get('name'),
                'title': article.get('title'),
                'description': article.get('description')
            })
            logger.debug(f"  Article: {article.get('title')} from {article.get('source', {}).get('name')}")
        
        logger.debug(f"Returning {len(formatted_articles)} formatted articles")
        return json.dumps(formatted_articles, indent=2)
            
    except Exception as e:
        logger.error(f"Error fetching news for '{entity_name}': {e}", exc_info=True)
        print(f"Error fetching news: {e}")
        return json.dumps([])


@function_tool
def fetch_article_content(url: str) -> str:
    """
    Fetch a URL and return parsed article text content for sentiment analysis.
    
    Args:
        url: The URL of the article to fetch
        
    Returns:
        String containing the article title and main text content
    """
    logger.info(f"TOOL CALL: fetch_article_content(url='{url[:50]}...')")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        logger.debug(f"Fetching URL: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        logger.debug(f"Response status: {response.status_code}")
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        logger.debug("Parsing HTML content with BeautifulSoup")
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extract title
        title = soup.find('title')
        title_text = title.string if title else "No title found"
        logger.debug(f"Article title: {title_text}")
        
        # Extract main content (article text)
        # Try common article containers
        article = soup.find('article') or soup.find('div', class_='article-content') or soup.find('div', class_='content')
        
        if article:
            text = article.get_text(separator='\n', strip=True)
            logger.debug("Extracted text from article container")
        else:
            text = soup.get_text(separator='\n', strip=True)
            logger.debug("Extracted text from full page")
        
        # Clean up whitespace
        text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
        
        original_length = len(text)
        # Limit text length to avoid token limits (first 2000 chars)
        if len(text) > 2000:
            text = text[:2000] + "..."
            logger.debug(f"Truncated text from {original_length} to 2000 characters")
        
        logger.info(f"✓ Successfully fetched and parsed article ({len(text)} chars)")
        return f"Title: {title_text}\n\nContent:\n{text}"
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching article from {url}: {e}", exc_info=True)
        return f"Error fetching article: {str(e)}"
