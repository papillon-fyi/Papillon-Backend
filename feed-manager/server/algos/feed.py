import os
import json
import httpx
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer
import asyncio
import time
from datetime import datetime, timezone
from server.models import Feed, FeedSource
from collections import defaultdict
import random
import math
import hashlib
import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

SEARCH_CACHE_TTL = 30  # 30 seconds for search results
FEED_CACHE_TTL = 300  # 5 minutes for long-term feed cache
RESPONSE_LIMIT = 10 # number of posts to be received from api response
FEED_LIMIT = 100 # number of total posts in a feed
MAX_PER_AUTHOR = 10 # max posts per author in a feed
MAX_AGE_SECONDS = 48 * 60 * 60  # 48 hours in seconds

# ONNX model setup
MODEL_PATH = os.path.join(os.path.dirname(__file__), "all-MiniLM-L6-v2.onnx")
TOKENIZER_NAME = "sentence-transformers/all-MiniLM-L6-v2"

tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME)
session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])

# API endpoints
FEEDS_API_BASE = "https://m0xinwa8l4.execute-api.us-east-1.amazonaws.com/production"
SUBSCRIPTIONS_API_BASE = "https://d1abpjglrf.execute-api.us-east-1.amazonaws.com/production"
PAPILLON_API_KEY = os.getenv("PAPILLON_API_KEY")

def extract_did_and_feedid_from_uri(feed_uri: str) -> tuple:
    """
    Extract DID and feedId from at:// URI.
    Example: at://did:plc:abc123/app.bsky.feed.generator/my-feed -> (did:plc:abc123, my-feed)
    """
    try:
        # Remove at:// prefix
        uri_parts = feed_uri.replace("at://", "").split("/")
        did = uri_parts[0]
        # Last part is the feedId
        feed_id = uri_parts[-1]
        return did, feed_id
    except (IndexError, AttributeError):
        return None, None

async def get_cache_from_api(cache_key: str, cache_type: str) -> dict:
    """
    Fetch cache entry from feeds API.
    
    Args:
        cache_key: The cache key (feed_uri for feed cache, query string for search cache)
        cache_type: Type of cache ('search' or 'feed')
    
    Returns:
        dict with cached data, or None if not found
    """
    if cache_type == 'feed':
        # cache_key is the feed_uri (at://did/app.bsky.feed.generator/feedId)
        did, feed_id = extract_did_and_feedid_from_uri(cache_key)
        if not did or not feed_id:
            return None
        
        try:
            headers = {"x-api-key": PAPILLON_API_KEY} if PAPILLON_API_KEY else {}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{FEEDS_API_BASE}/feeds/{did}/{feed_id}", headers=headers)
                if response.status_code == 200:
                    feed_data = response.json()
                    # Return the cache object if it exists
                    if 'cache' in feed_data:
                        return feed_data.get('cache')
                return None
        except Exception as e:
            print(f"Error fetching feed cache from API: {e}")
            return None
    
    # For search cache, we don't have a good place to store it yet
    # Could be stored in feed metadata or separate cache table
    return None

async def set_cache_to_api(cache_key: str, cache_type: str, data: dict, ttl: int = None) -> bool:
    """
    Store cache entry to feeds API.
    
    Args:
        cache_key: The cache key (feed_uri for feed cache, query string for search cache)
        cache_type: Type of cache ('search' or 'feed')
        data: The data to cache
        ttl: Time-to-live in seconds (optional, not used yet)
    
    Returns:
        bool indicating success
    """
    if cache_type == 'feed':
        # cache_key is the feed_uri (at://did/app.bsky.feed.generator/feedId)
        did, feed_id = extract_did_and_feedid_from_uri(cache_key)
        if not did or not feed_id:
            return False
        
        try:
            headers = {"x-api-key": PAPILLON_API_KEY} if PAPILLON_API_KEY else {}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{FEEDS_API_BASE}/feeds/{did}/{feed_id}/cache",
                    json={"cache": data},
                    headers=headers
                )
                return response.status_code == 200
        except Exception as e:
            print(f"Error setting feed cache via API: {e}")
            return False
    
    # For search cache, we don't have a good place to store it yet
    return True

def detect_and_expand_acronyms(topic_preferences: list[dict], original_prompt: str = None) -> list[dict]:
    """
    Use LLM to detect acronyms in topic preferences and expand them with semantic context.
    Returns updated topic preferences with is_acronym flag and expanded search terms.
    """
    if not topic_preferences or not original_prompt:
        return topic_preferences
    
    topic_names = [t['name'] for t in topic_preferences]
    
    prompt = f"""Given this user's feed intent:
"{original_prompt}"

And these extracted topic preferences: {', '.join(topic_names)}

Analyze each topic and determine:
1. Is it an acronym that needs disambiguation? (e.g., CHI, NBA, AI, ML)
2. If yes, what is the full semantic meaning based on the context?
3. What search terms would best capture the user's intent?

Provide ONLY valid JSON with this structure:
{{
  "topics": [
    {{
      "name": "original_topic",
      "is_acronym": true/false,
      "search_terms": "expanded search terms if acronym, otherwise same as name",
      "explanation": "brief reason"
    }}
  ]
}}

For acronyms, expand them semantically (e.g., "CHI" → "CHI conference human-computer interaction HCI research").
For regular terms, keep the search_terms the same as name.
"""
    
    try:
        response = openai.chat.completions.create(
            model="gpt-5-nano",
            messages=[{"role": "user", "content": prompt}],
        )
        
        result = json.loads(response.choices[0].message.content.strip())
        
        # Update topic preferences with LLM analysis
        updated_topics = []
        for topic in topic_preferences:
            matching = next((t for t in result['topics'] if t['name'] == topic['name']), None)
            if matching:
                updated_topics.append({
                    **topic,
                    'is_acronym': 1 if matching.get('is_acronym') else 0,
                    'context': matching.get('search_terms') if matching.get('is_acronym') else None
                })
            else:
                updated_topics.append({**topic, 'is_acronym': 0, 'context': None})
        
        return updated_topics
        
    except Exception as e:
        print(f"[Acronym Detection Error] {e}")
        # Return original topics if LLM fails
        return [{**t, 'is_acronym': 0, 'context': None} for t in topic_preferences]

def compute_blueprint_hash(feed_uri: str) -> str:
    """Compute a deterministic hash of the feed blueprint (sources + ranking_weights)."""
    # Get all sources for this feed
    sources = (
        FeedSource
        .select()
        .join(Feed)
        .where(Feed.uri == feed_uri)
        .order_by(FeedSource.source_type, FeedSource.identifier)  # Ensure consistent ordering
    )
    
    # Build a deterministic representation of the blueprint
    blueprint_data = {
        "sources": [
            {
                "type": src.source_type,
                "identifier": src.identifier,
                "weight": src.weight
            }
            for src in sources
        ],
        "ranking_weights": get_ranking_weights(feed_uri)
    }
    
    # Convert to JSON string with sorted keys for consistency
    blueprint_json = json.dumps(blueprint_data, sort_keys=True)
    
    # Compute SHA256 hash
    return hashlib.sha256(blueprint_json.encode()).hexdigest()

def encode_onnx(texts):
    """Return embedding vectors using the ONNX model."""
    if isinstance(texts, str):
        texts = [texts]
    inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="np")
    outputs = session.run(None, dict(inputs))
    embeddings = outputs[0]
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings = embeddings / norms
    return embeddings


async def fetch_post_by_identifier(repo: str, rkey: str) -> dict:
    """Return minimal post info (just enough to build a URI)."""
    uri = f"at://{repo}/app.bsky.feed.post/{rkey}"
    return {"uri": uri, "repo": repo, "rkey": rkey}


async def fetch_full_post(uri: str) -> dict:
    """Fetch full post JSON so keyword filters can work."""
    url = (
        "https://public.api.bsky.app/xrpc/"
        "app.bsky.feed.getPosts"
        f"?uris={uri}"
    )
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url)

    if r.status_code != 200:
        return {}

    posts = r.json().get("posts", [])
    return posts[0] if posts else {}


async def fetch_author_posts(actor_did: str, limit: int = RESPONSE_LIMIT) -> list[dict]:
    """Fetch posts from a Bluesky author DID."""
    url = (
        "https://public.api.bsky.app/xrpc/"
        "app.bsky.feed.getAuthorFeed"
        f"?actor={actor_did}&limit={limit}"
    )
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url)

    if r.status_code != 200:
        print("Author fetch failed:", r.text)
        return []

    items = r.json().get("feed", [])
    results = []

    for item in items:
        post = item.get("post")
        if not post:
            continue
        uri = post.get("uri")
        if not uri:
            continue
        try:
            _, _, repo, _, rkey = uri.split("/", 4)
        except ValueError:
            continue

        results.append(await fetch_post_by_identifier(repo, rkey))

    return results


async def search_vector(query: str, access_jwt: str = None, limit: int = RESPONSE_LIMIT) -> list[dict]:
    """Use Bluesky searchPosts API to find relevant posts, returning minimal identifiers.
    Note: Bluesky's searchPosts is text-based; we use it for both text and semantic queries.
    """
    if not access_jwt:
        print("Warning: No access JWT provided for search")
        return []
    
    # Check cache via API
    cache_key = f"vector:{query}"
    cached = await get_cache_from_api(cache_key, 'search')
    if cached and (time.time() - cached.get('timestamp', 0)) < SEARCH_CACHE_TTL:
        cached_results = cached.get('data', [])
        return [await fetch_post_by_identifier(r['repo'], r['rkey']) for r in cached_results[:limit]]

    # Fetch from Bluesky API
    url = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"
    headers = {"Authorization": f"Bearer {access_jwt}"}
    params = {"q": query, "limit": limit}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, headers=headers, params=params)
    except httpx.TimeoutException:
        print(f"Search timeout for query: {query}")
        return []

    if r.status_code != 200:
        print(f"Search failed: {r.status_code} - {r.text}")
        return []

    results = []
    posts = r.json().get("posts", [])[:limit]
    api_results = []
    
    for post in posts:
        uri = post.get("uri")
        if not uri:
            continue
        try:
            _, _, repo, _, rkey = uri.split("/", 4)
            api_results.append({"repo": repo, "rkey": rkey})
            results.append(await fetch_post_by_identifier(repo, rkey))
        except ValueError:
            continue

    # Cache the API results
    await set_cache_to_api(
        cache_key=f"vector:{query}",
        cache_type='search',
        data={'data': api_results, 'timestamp': int(time.time())},
        ttl=SEARCH_CACHE_TTL
    )

    return results


async def search_text(query: str, access_jwt: str = None, limit: int = RESPONSE_LIMIT) -> list[dict]:
    """Use Bluesky searchPosts API to find relevant posts, returning minimal identifiers."""
    if not access_jwt:
        print("Warning: No access JWT provided for search")
        return []
    
    # Check cache via API
    cache_key = f"text:{query}"
    cached = await get_cache_from_api(cache_key, 'search')
    if cached and (time.time() - cached.get('timestamp', 0)) < SEARCH_CACHE_TTL:
        cached_results = cached.get('data', [])
        return [await fetch_post_by_identifier(r['repo'], r['rkey']) for r in cached_results[:limit]]

    # Fetch from Bluesky API
    url = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"
    headers = {"Authorization": f"Bearer {access_jwt}"}
    params = {"q": query, "limit": limit}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, headers=headers, params=params)
    except httpx.TimeoutException:
        print(f"Search timeout for query: {query}")
        return []

    if r.status_code != 200:
        print(f"Search failed: {r.status_code} - {r.text}")
        return []

    results = []
    posts = r.json().get("posts", [])[:limit]
    api_results = []
    
    for post in posts:
        uri = post.get("uri")
        if not uri:
            continue
        try:
            _, _, repo, _, rkey = uri.split("/", 4)
            api_results.append({"repo": repo, "rkey": rkey})
            results.append(await fetch_post_by_identifier(repo, rkey))
        except ValueError:
            continue

    # Cache the API results
    await set_cache_to_api(
        cache_key=f"text:{query}",
        cache_type='search',
        data={'data': api_results, 'timestamp': int(time.time())},
        ttl=SEARCH_CACHE_TTL
    )

    return results


# Filtering logic (blacklist plcs + keywords)
def extract_filters(feed_uri: str):
    """Return sets for quick filtering."""
    rows = (
        FeedSource
        .select()
        .where(FeedSource.feed == Feed.get(Feed.uri == feed_uri))
    )
    blocked_dids = set()
    banned_keywords = set()
    for r in rows:
        if r.source_type == "profile_filter":
            blocked_dids.add(r.identifier)
        if r.source_type == "topic_filter":
            banned_keywords.add(r.identifier.lower())

    return blocked_dids, banned_keywords

def should_block_post(full_post: dict, blocked_dids: set, banned_keywords: set) -> bool:
    """Return True if post should be filtered out."""
    # Block authors
    author = full_post.get("author")
    if author:
        if author.get("did") in blocked_dids:
            return True
    # Block keyword-containing posts
    record = full_post.get("record", {})
    text = record.get("text", "").lower()

    for kw in banned_keywords:
        if kw in text:
            return True

    return False

def get_ranking_weights(feed_uri: str) -> dict:
    """Get ranking weights for a feed, with defaults."""
    try:
        feed = Feed.get(Feed.uri == feed_uri)
        if feed.ranking_weights:
            return json.loads(feed.ranking_weights)
    except:
        pass
    # Default weights (must sum to 1.0)
    return {"relevance": 0.5, "popularity": 0.3, "recency": 0.2}

def compute_relevance_score(full_post: dict, topic_preferences: list, profile_preferences: set) -> float:
    """Compute relevance score based on topic/profile match."""
    score = 0.0
    
    # Check if post is from a preferred profile
    author_did = full_post.get("author", {}).get("did")
    if author_did and author_did in profile_preferences:
        score += 1.0
    
    # Check topic relevance using simple text matching
    text = full_post.get("record", {}).get("text", "").lower()
    if text:
        for topic_pref in topic_preferences:
            topic_name = topic_pref["name"].lower()
            topic_weight = topic_pref["weight"]
            if topic_name in text:
                score += topic_weight
    
    return min(score, 1.0)  # Cap at 1.0

def compute_ranking_score(full_post: dict, post_time: float, now: float, 
                         ranking_weights: dict, topic_preferences: list, 
                         profile_preferences: set) -> float:
    """Compute composite ranking score based on relevance, popularity, and recency."""
    
    # Relevance score (0-1)
    relevance = compute_relevance_score(full_post, topic_preferences, profile_preferences)
    
    # Popularity score (0-1) - based on engagement metrics
    like_count = full_post.get("likeCount", 0)
    reply_count = full_post.get("replyCount", 0)
    repost_count = full_post.get("repostCount", 0)
    quote_count = full_post.get("quoteCount", 0)
    
    # Total engagement
    total_engagement = like_count + (reply_count * 2) + (repost_count * 3) + (quote_count * 2)
    # Normalize using log scale (caps around 1.0 for ~100+ engagements)
    popularity = min(math.log1p(total_engagement) / 5.0, 1.0)
    
    # Recency score (0-1) - exponential decay over 48 hours
    age_seconds = now - post_time
    recency = math.exp(-age_seconds / (MAX_AGE_SECONDS / 3))  # Decay over ~16 hours to 0.05
    recency = max(0.0, min(recency, 1.0))
    
    # Weighted combination
    w_relevance = ranking_weights.get("relevance", 0.5)
    w_popularity = ranking_weights.get("popularity", 0.5)
    w_recency = ranking_weights.get("recency", 0.5)
    
    # Normalize weights to sum to 1
    total_weight = w_relevance + w_popularity + w_recency
    if total_weight > 0:
        w_relevance /= total_weight
        w_popularity /= total_weight
        w_recency /= total_weight
    else:
        # If all weights are 0, use equal weighting
        w_relevance = w_popularity = w_recency = 1.0 / 3.0
    
    score = (relevance * w_relevance) + (popularity * w_popularity) + (recency * w_recency)
    
    return score

# Feed handler factory
def make_handler(feed_uri: str):
    build_lock = asyncio.Lock()  # Prevent concurrent builds for the same feed
    build_in_progress = False

    async def maybe_build_feed(force=False):
        nonlocal build_in_progress

        async with build_lock:
            if build_in_progress:
                return None
            build_in_progress = True

        try:
            return await build_feed(FEED_LIMIT)
        finally:
            async with build_lock:
                build_in_progress = False



    async def build_feed(limit=RESPONSE_LIMIT):
        """Build fresh feed skeleton by fetching sources + posts."""
        # Get feed to access access_jwt
        feed = Feed.get(Feed.uri == feed_uri)
        access_jwt = feed.access_jwt if feed else None
        
        sources = (
            FeedSource
            .select()
            .join(Feed)
            .where(Feed.uri == feed_uri)
        )

        # Get ranking weights for this feed
        ranking_weights = get_ranking_weights(feed_uri)
        
        # Build lists for relevance computation
        topic_preferences = []
        profile_preferences = set()
        for src in sources:
            if src.source_type == "topic_preference":
                topic_preferences.append({"name": src.identifier, "weight": src.weight})
            elif src.source_type == "profile_preference":
                profile_preferences.add(src.identifier)

        # Load blacklist rules
        blocked_dids, banned_keywords = extract_filters(feed_uri)

        collected = []
        author_counts = defaultdict(int)

        # Fetch posts concurrently
        tasks = []
        seen_queries = set()
        for src in sources:
            if src.source_type == "profile_preference":
                tasks.append(fetch_author_posts(src.identifier, limit))
            elif src.source_type == "topic_preference":
                if src.identifier not in seen_queries:
                    # Check if this is an acronym
                    is_acronym = getattr(src, 'is_acronym', 0)
                    context = getattr(src, 'context', None)
                    
                    if is_acronym:
                        # For acronyms: ONLY use vector search, optionally with context
                        query = f"{context} {src.identifier}" if context else src.identifier
                        tasks.append(search_vector(query, access_jwt, limit))
                    else:
                        # For regular terms: use both text and vector search
                        tasks.append(search_text(src.identifier, access_jwt, limit))
                        tasks.append(search_vector(src.identifier, access_jwt, limit))
                    
                    seen_queries.add(src.identifier)
        results = await asyncio.gather(*tasks)

        for r in results:
            collected.extend(r)

        # Deduplicate collected posts before fetching full posts
        collected = list({p["uri"]: p for p in collected}.values())

        # Dynamically scale collection size based on MAX_PER_AUTHOR
        # Lower MAX_PER_AUTHOR = stricter filtering = need more posts
        collection_multiplier = max(2, 10 // MAX_PER_AUTHOR)
        target_collected = FEED_LIMIT * collection_multiplier
        if len(collected) > target_collected:
            collected = random.sample(collected, target_collected)

        # Fetch full posts with concurrency limit to avoid overwhelming API
        sem = asyncio.Semaphore(10)

        async def fetch_with_sem(uri):
            async with sem:
                return await fetch_full_post(uri)

        full_posts = await asyncio.gather(*[fetch_with_sem(p["uri"]) for p in collected])

        filtered_posts = []
        author_counts = defaultdict(int)

        for p, full_post in zip(collected, full_posts):

            if should_block_post(full_post, blocked_dids, banned_keywords):
                continue

            # Parse and check createdAt for recency
            created_at_str = full_post.get("record", {}).get("createdAt")
            if not created_at_str:
                continue
            try:
                post_time = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")).timestamp()
                now = datetime.now(timezone.utc).timestamp()
                if now - post_time > MAX_AGE_SECONDS:
                    continue
            except ValueError:
                continue

            author_did = full_post.get("author", {}).get("did")
            if author_did:
                if author_counts[author_did] >= MAX_PER_AUTHOR:
                    continue
                author_counts[author_did] += 1

            # Compute ranking score
            rank_score = compute_ranking_score(
                full_post, post_time, now, ranking_weights, 
                topic_preferences, profile_preferences
            )

            # Store full_post with URI, timestamp, and rank score for sorting
            filtered_posts.append({
                "uri": p["uri"],
                "timestamp": post_time,
                "rank_score": rank_score
            })

            if len(filtered_posts) >= FEED_LIMIT:
                break

        # Sort posts by ranking score (highest first), then by recency
        filtered_posts.sort(key=lambda x: (x["rank_score"], x["timestamp"]), reverse=True)

        # Compute oldest timestamp for cache validation
        oldest_timestamp = None
        if filtered_posts:
            oldest_timestamp = int(min(p["timestamp"] for p in filtered_posts))

        # Format for Bluesky
        feed = {
            "cursor": "0",
            "feed": [{"post": p["uri"]} for p in filtered_posts[:FEED_LIMIT]]
        }

        # Compute current blueprint hash
        current_blueprint_hash = compute_blueprint_hash(feed_uri)

        # Save to cache via API
        await set_cache_to_api(
            cache_key=feed_uri,
            cache_type='feed',
            data={
                'feed': feed,
                'timestamp': int(time.time()),
                'oldest_timestamp': oldest_timestamp,
                'blueprint_hash': current_blueprint_hash
            },
            ttl=FEED_CACHE_TTL
        )

        return feed

    async def serve_from_cache(limit=10):
        """Return cached feed if recent, blueprint matches, and posts are fresh, otherwise None."""
        cached = await get_cache_from_api(feed_uri, 'feed')
        if cached is None:
            return None

        # Check if blueprint has changed - if so, invalidate cache
        current_blueprint_hash = compute_blueprint_hash(feed_uri)
        if cached.get('blueprint_hash') != current_blueprint_hash:
            print(f"Blueprint changed for {feed_uri}, invalidating cache")
            return None

        cached_feed = cached.get('feed')
        if not cached_feed:
            return None
        
        feed_items = cached_feed.get("feed", [])
        if not feed_items:
            return None

        # Check if the oldest post in cache is within 48 hours using stored timestamp
        oldest_timestamp = cached.get('oldest_timestamp')
        if oldest_timestamp is not None:
            if time.time() - oldest_timestamp > MAX_AGE_SECONDS:
                return None  # Cache has stale posts
        else:
            # Fallback: fetch the oldest post to check timestamp (for backwards compatibility)
            oldest_uri = feed_items[-1].get("post")
            if oldest_uri:
                oldest_full = await fetch_full_post(oldest_uri)
                if oldest_full:
                    created_at_str = oldest_full.get("record", {}).get("createdAt")
                    if created_at_str:
                        try:
                            oldest_time = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")).timestamp()
                            now = datetime.now(timezone.utc).timestamp()
                            if now - oldest_time > MAX_AGE_SECONDS:
                                return None  # Cache has stale posts
                        except ValueError:
                            return None

        return cached_feed

    async def handler(cursor=None, limit=RESPONSE_LIMIT):
        # Normalize cursor to integer
        try:
            start = int(cursor)
        except (ValueError, TypeError):
            start = 0

        limit = int(limit)
        cached = await serve_from_cache()  # always check for any available cache

        if not cached:
            # No valid cache, rebuild immediately
            await maybe_build_feed(force=True)
            cached = await serve_from_cache()

        else:
            # Check if cache is over 5 minutes old, trigger background rebuild
            cached_data = await get_cache_from_api(feed_uri, 'feed')
            if cached_data and (time.time() - cached_data.get('timestamp', 0)) > FEED_CACHE_TTL:
                asyncio.create_task(maybe_build_feed())  # Background rebuild

        feed_items = cached.get("feed", [])

        # Slice the feed according to cursor + limit
        page = feed_items[start:start + limit]

        # Compute next cursor
        if start + limit >= len(feed_items):
            next_cursor = "0"  # must always be a string
        else:
            next_cursor = str(start + limit)

        return {
            "cursor": next_cursor,
            "feed": page,
        }

    return handler
