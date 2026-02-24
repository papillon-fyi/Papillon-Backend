import os
import json
import datetime
import asyncio
import httpx
import numpy as np
import onnxruntime as ort
import openai
from transformers import AutoTokenizer
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# Configuration
openai.api_key = os.getenv("OPENAI_API_KEY")

# Bluesky API endpoints
BSKY_API_BASE = "https://public.api.bsky.app/xrpc"

# Load ONNX model setup
MODEL_PATH = os.path.join(os.path.dirname(__file__), "all-MiniLM-L6-v2.onnx")
TOKENIZER_NAME = "sentence-transformers/all-MiniLM-L6-v2"

tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME)
session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])

def encode_onnx(texts):
    """Return normalized embedding vectors using ONNX model."""
    if isinstance(texts, str):
        texts = [texts]
    inputs = tokenizer(
        texts,
        padding=True,
        truncation=True,
        return_tensors="np",
    )
    outputs = session.run(None, dict(inputs))
    token_embeddings = outputs[0]  # Shape: (batch_size, seq_len, hidden_size)
    attention_mask = inputs['attention_mask']
    
    # Mean pooling: take attention mask into account for correct averaging
    input_mask_expanded = np.expand_dims(attention_mask, -1)
    sum_embeddings = np.sum(token_embeddings * input_mask_expanded, axis=1)
    sum_mask = np.clip(np.sum(input_mask_expanded, axis=1), a_min=1e-9, a_max=None)
    embeddings = sum_embeddings / sum_mask
    
    # Normalize
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings = embeddings / norms
    return embeddings

def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

async def fetch_recent_posts(client: httpx.AsyncClient, did: str, limit: int = 2) -> list[str]:
    """Fetch recent posts from an account."""
    url = f"{BSKY_API_BASE}/app.bsky.feed.getAuthorFeed"
    params = {"actor": did, "limit": limit}
    try:
        r = await client.get(url, params=params, timeout=10.0)
        if r.status_code != 200:
            print(f"  ⚠️  Failed to fetch posts for {did[:20]}...: HTTP {r.status_code}")
            return []
        data = r.json()
        posts = []
        for item in data.get("feed", []):
            post = item.get("post", {})
            record = post.get("record", {})
            text = record.get("text", "")
            if text:
                posts.append(text)
        if not posts:
            print(f"  ⚠️  No posts found for {did[:20]}...")
        return posts
    except Exception as e:
        print(f"  ❌ Error fetching posts for {did[:20]}...: {e}")
        return []

async def fetch_and_score_authors(client: httpx.AsyncClient, query: str, limit: int = 3) -> list[tuple[str, float, list[float]]]:
    """
    Search for actors using Bluesky API, then rank them by cosine similarity
    of their recent posts to the query. Returns list of (DID, score, embedding).
    """
    url = f"{BSKY_API_BASE}/app.bsky.actor.searchActors"
    params = {"q": query, "limit": limit}
    
    try:
        r = await client.get(url, params=params)
        if r.status_code != 200:
            print(f"  ❌ Search failed: HTTP {r.status_code}")
            return []
        
        data = r.json()
        actors = data.get("actors", [])
        
        if not actors:
            print(f"  ⚠️  No actors found for '{query}'")
            return []
        
        print(f"  Found {len(actors)} actors for '{query}', fetching posts...")
        
        # Get query embedding - already normalized by encode_onnx
        query_embedding = encode_onnx(query)[0]
        
        # Limit concurrent requests to avoid overwhelming the API
        semaphore = asyncio.Semaphore(5)
        
        # Fetch posts for all actors in parallel with concurrency limit
        async def fetch_actor_posts(actor):
            async with semaphore:
                did = actor.get("did")
                if not did:
                    return None
                
                posts = await fetch_recent_posts(client, did, limit=2)
                if not posts:
                    return None
                
                # Concatenate posts
                concat_posts = " ".join(posts)
                return (did, concat_posts)
        
        # Fetch all posts in parallel
        results = await asyncio.gather(*[fetch_actor_posts(actor) for actor in actors])
        actor_posts = [r for r in results if r is not None]
        
        if not actor_posts:
            print(f"  ⚠️  No actors with posts found")
            return []
        
        print(f"  → Fetched posts from {len(actor_posts)}/{len(actors)} actors")
        
        # Batch encode all concatenated posts at once (much faster than individual encoding)
        dids = [did for did, _ in actor_posts]
        all_posts = [posts for _, posts in actor_posts]
        account_embeddings = encode_onnx(all_posts)  # Batch encoding
        
        # Compute similarities for all accounts
        actor_data = []
        for did, embedding in zip(dids, account_embeddings):
            # Both embeddings are already normalized, so dot product = cosine similarity
            similarity = float(np.dot(query_embedding, embedding))
            if similarity > 0:  # Filter negative scores early
                actor_data.append((did, similarity, embedding.tolist()))
        
        print(f"  → Kept {len(actor_data)} actors with positive scores")
        
        # Sort by similarity score (descending)
        actor_data.sort(key=lambda x: x[1], reverse=True)
        return actor_data[:2]  # Return top 2
        
    except Exception as e:
        print(f"  ❌ Error in fetch_and_score_authors: {e}")
        return []

async def generate_feed_ruleset(query: str) -> dict:
    """Generates the feed ruleset JSON including suggested authors."""
    # LLM prompt
    llm_prompt = f"""
    The user described their ideal feed as follows:
    "{query}"

    Your task: produce ONLY valid JSON (no commentary or markdown).

    The JSON must contain the following top-level fields:

    {{
    "record_name": string,
    "display_name": string,
    "description": string,
    "topic_preferences": [
        {{ "name": string, "weight": float between 0.3 and 1.0 }}
    ],
    "topic_filters": [
        {{ "name": string, "weight": float (0.5 default) }}
    ],
    "ranking_weights": {{
        "relevance": float,
        "popularity": float,
        "recency": float
    }}
    }}

    Rules:
    - topic_preferences should represent meaningful subjects, entities, themes, or interests from the user's prompt. Keep to 5 topics, 1-2 words each.
    - topic_filters are topics or concepts the user wants to avoid or limit. Put these in topic_filters array.
    - Avoid generic action words unless actually thematic to the primary interests mentioned.
    - Display name must be less than 5 words.
    - record_name must be lowercase-with-hyphens, filesystem-safe, and contain no spaces.
    - ranking_weights MUST sum to exactly 1.0. Use defaults: relevance=0.5, popularity=0.3, recency=0.2 unless user specifies otherwise.
    - Output ONLY valid JSON.
    """

    response = openai.chat.completions.create(
        model="gpt-5-nano",
        messages=[{"role": "user", "content": llm_prompt}],
    )

    raw_text = response.choices[0].message.content.strip()
    try:
        feed_fields = json.loads(raw_text)
    except json.JSONDecodeError:
        raise ValueError("GPT did not return valid JSON:\n" + raw_text)

    # Add metadata
    feed_fields["original_prompt"] = query
    feed_fields["generated_at"] = datetime.datetime.utcnow().isoformat()

    # Normalize ranking_weights to ensure they sum to exactly 1.0
    if "ranking_weights" in feed_fields:
        weights = feed_fields["ranking_weights"]
        total = weights.get("relevance", 0.5) + weights.get("popularity", 0.3) + weights.get("recency", 0.2)
        if total > 0:
            weights["relevance"] = weights.get("relevance", 0.5) / total
            weights["popularity"] = weights.get("popularity", 0.3) / total
            weights["recency"] = weights.get("recency", 0.2) / total
    else:
        # Set defaults
        feed_fields["ranking_weights"] = {
            "relevance": 0.5,
            "popularity": 0.3,
            "recency": 0.2
        }

    # Fetch suggested accounts per topic (more targeted searches)
    print("\n" + "="*60)
    print("FETCHING SUGGESTED ACCOUNTS")
    print("="*60)
    
    topic_queries = [t["name"] for t in feed_fields.get("topic_preferences", [])]
    print(f"Searching for accounts matching topics: {', '.join(topic_queries)}\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Search for each topic in parallel, get top 3 accounts per topic (reduced from 5)
        results = await asyncio.gather(*[fetch_and_score_authors(client, topic, limit=3) for topic in topic_queries])
    
    # Collect all unique accounts with their best scores and embeddings
    account_map = {}  # did -> (best_score, embedding)
    for topic_results in results:
        for did, score, embedding in topic_results:
            if did not in account_map or score > account_map[did][0]:
                account_map[did] = (score, embedding)
    
    # Convert to sorted list and filter out negative or zero scores
    all_accounts = [(did, score, emb) for did, (score, emb) in account_map.items() if score > 0]
    all_accounts.sort(key=lambda x: x[1], reverse=True)
    
    print(f"✓ Found {len(all_accounts)} unique accounts with positive scores across all topics\n")
    
    # Add profile_preferences with scores (only positive scores)
    if all_accounts:
        feed_fields["profile_preferences"] = [
            {
                "did": did,
                "score": score
            }
            for did, score, embedding in all_accounts
        ]

    # Remove name/description from blueprint
    blueprint = dict(feed_fields)
    blueprint.pop("record_name", None)
    blueprint.pop("display_name", None)
    blueprint.pop("description", None)

    # Final response
    final_output = {
        "record_name": feed_fields["record_name"],
        "display_name": feed_fields["display_name"],
        "description": feed_fields["description"],
        "blueprint": blueprint
    }

    return final_output

# Example usage
async def main():
    prompt = (
        "Show me posts about indie game development and pixel art. Skip NFT content."
    )
    result = await generate_feed_ruleset(query=prompt)
    print(json.dumps(result, indent=4))


if __name__ == "__main__":
    asyncio.run(main())
