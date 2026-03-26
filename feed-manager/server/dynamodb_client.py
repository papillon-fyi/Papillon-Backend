"""
Feeds API client for reading feed data from AWS via HTTP.
Replaces direct DynamoDB access with API calls to feeds-api Lambda.

This runs on Google Cloud and makes HTTP requests to the feeds-api.
Requires:
- FEEDS_API_URL (e.g., https://m0xinwa8l4.execute-api.us-east-1.amazonaws.com/production)
- PAPILLON_API_KEY (for authentication)
"""
import httpx
import os
from typing import Dict, List, Optional

FEEDS_API_URL = os.getenv('FEEDS_API_URL', 'https://m0xinwa8l4.execute-api.us-east-1.amazonaws.com/production')
API_KEY = os.getenv('PAPILLON_API_KEY', '')


async def get_all_feed_uris() -> List[str]:
    """
    Get all feed URIs by scanning all users.
    Makes multiple API calls to get feeds for each user.
    """
    # TODO: Add a /feeds/all endpoint to feeds-api for efficiency
    # For now, this is a placeholder that returns empty
    # Feed handlers will be created dynamically when feeds are deployed
    return []


async def get_feed_by_uri(feed_uri: str) -> Optional[Dict]:
    """
    Get feed data for a specific URI from feeds-api.
    Uses the new /feeds/by-uri endpoint.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{FEEDS_API_URL}/feeds/by-uri",
                params={"uri": feed_uri},
                headers={"x-api-key": API_KEY},
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'uri': data.get('uri'),
                    'did': data.get('did'),
                    'feed_id': data.get('feedId'),
                    'name': data.get('name'),
                    'description': data.get('description'),
                    'ruleset': data.get('ruleset', {})
                }
            elif response.status_code == 404:
                print(f"Feed not found: {feed_uri}")
                return None
            else:
                print(f"Error fetching feed: {response.status_code}")
                return None
    except Exception as e:
        print(f"Error fetching feed from API: {e}")
        return None


async def get_feed_sources(feed_uri: str) -> Dict[str, List]:
    """
    Extract sources from the feed's ruleset (blueprint).
    Returns dict with topic_preferences, profile_preferences, etc.
    """
    try:
        feed_data = await get_feed_by_uri(feed_uri)
        
        if not feed_data:
            return {
                'topic_preferences': [],
                'profile_preferences': [],
                'topic_filters': [],
                'profile_filters': [],
                'ranking_weights': {
                    'relevance': 0.5,
                    'popularity': 0.3,
                    'recency': 0.2
                }
            }
        
        ruleset = feed_data.get('ruleset', {})
        
        return {
            'topic_preferences': ruleset.get('topic_preferences', []),
            'profile_preferences': ruleset.get('profile_preferences', []),
            'topic_filters': ruleset.get('topic_filters', []),
            'profile_filters': ruleset.get('profile_filters', []),
            'ranking_weights': ruleset.get('ranking_weights', {
                'relevance': 0.5,
                'popularity': 0.3,
                'recency': 0.2
            })
        }
    except Exception as e:
        print(f"Error getting feed sources: {e}")
        return {
            'topic_preferences': [],
            'profile_preferences': [],
            'topic_filters': [],
            'profile_filters': [],
            'ranking_weights': {'relevance': 0.5, 'popularity': 0.3, 'recency': 0.2}
        }
