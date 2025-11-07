import requests
from traceback import format_exc

def get_entity_news_from_api(entity_name: str, num_results: int = 10) -> list:
    """
    Fetch news articles for an entity using NewsAPI (free tier available).
    
    Args:
        entity_name (str): Entity name
        num_results (int): Number of results to fetch
        
    Returns:
        list: List of dicts with 'title', 'url', 'source', 'description', 'published_at'
    """
    
    # Get free API key from https://newsapi.org
    API_KEY = "48c51ab301094753bb46f899b6b5a103"  # Sign up free at newsapi.org
    
    url = "https://newsapi.org/v2/everything"
    
    # Search parameters
    params = {
        'q': entity_name,
        'sortBy': 'publishedAt',
        'language': 'en',
        'pageSize': num_results,
        'apiKey': API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)  # Increased from 10 to 30 seconds
        response.raise_for_status()
        data = response.json()
        
        if data['status'] != 'ok':
            print(f"API Error: {data.get('message', 'Unknown error')}")
            return []
        
        articles = []
        for article in data['articles']:
            articles.append({
                'title': article['title'],
                'url': article['url'],
                'source': article['source']['name'],
                'description': article['description'],
                'published_at': article['publishedAt'],
                'image': article.get('urlToImage')
            })
        
        return articles
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching news: {e}")
        return []


# Alternative: Using GNews API (simpler, no key sometimes needed)
def get_entity_news_from_gnews(entity_name: str, num_results: int = 10) -> list:
    """
    Fetch news using GNews API (faster, simpler).
    
    Args:
        entity_name (str): Entity name
        num_results (int): Number of results
        
    Returns:
        list: News articles
    """
    
    url = "https://gnews.io/api/v4/search"
    
    params = {
        'q': entity_name,
        'lang': 'en',
        'max': num_results,
        'apikey': 'db2651be6ce35c4956fbe1fc2a5a8cdb'  # Free key from https://gnews.io
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)  # Increased from 10 to 30 seconds
        response.raise_for_status()
        data = response.json()
        
        return data.get('articles', [])
            
    except Exception as e:
        print(format_exc(e))
        print(f"Error: {e}")
        return []
