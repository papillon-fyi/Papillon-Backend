# Papillon Feeds API

AWS Lambda API for managing Papillon feeds in DynamoDB.

## Database Structure

**Table**: `papillon-accounts`

**Primary Key**: `did` (String)

**Attributes**:

- `did`: User's Decentralized Identifier
- `feeds`: Map of feed IDs to feed objects
  - Each feed has:
    - `ruleset`: JSON blueprint (what feed-manager API expects)
    - `cache`: Array of post URIs (updated by feed-manager)
- `createdAt`: ISO timestamp
- `updatedAt`: ISO timestamp

**Default Feed**: Every account has a `papillon-feed` by default.

## API Endpoints

### Health Check

- `GET /health` - Returns health status

### Feed Ruleset Generation

- `POST /feeds/generate-ruleset` - Generate a feed ruleset using AI and Bluesky search

  ```json
  {
    "query": "Show me posts about indie game development and pixel art. Skip NFT content."
  }
  ```

  Returns:

  ```json
  {
    "record_name": "indie-gamedev-pixel-art",
    "display_name": "Indie Game Dev & Pixel Art",
    "description": "Posts about indie game development and pixel art, excluding NFT content",
    "blueprint": {
      "topic_preferences": [
        { "name": "indie games", "weight": 0.9 },
        { "name": "pixel art", "weight": 0.8 }
      ],
      "topic_filters": [{ "name": "NFT", "weight": 0.5 }],
      "profile_preferences": [
        { "did": "did:plc:abc123...", "weight": 1.0 },
        { "did": "did:plc:def456...", "weight": 0.9 },
        { "did": "did:plc:ghi789...", "weight": 0.8 }
      ],
      "ranking_weights": {
        "relevance": 0.5,
        "popularity": 0.3,
        "recency": 0.2
      },
      "original_prompt": "...",
      "generated_at": "2026-03-24T12:34:56.789Z"
    }
  }
  ```

  **How it works:**
  1. Uses OpenAI to extract topics, filters, and ranking preferences from the query
  2. Searches Bluesky API for accounts matching each identified topic (5 per topic)
  3. Assigns variable weights: top search results get higher weights (1.0 → 0.6)
  4. If an account appears in multiple topic searches, keeps the highest weight
  5. Returns top 10 unique accounts sorted by weight as profile_preferences
  6. No ML embeddings required - uses Bluesky's native search relevance

### Feed Deployment

- `POST /feeds/deploy` - Deploy a feed to Bluesky and store it in DynamoDB

  ```json
  {
    "did": "did:plc:user123",
    "feedId": "my-custom-feed",
    "feedName": "Indie Gaming Feed",
    "feedDescription": "A feed about indie games and pixel art",
    "tunings": [
      { "id": "1", "type": "topic", "label": "indie games", "value": 90 },
      { "id": "2", "type": "topic", "label": "pixel art", "value": 80 },
      { "id": "3", "type": "topic", "label": "NFT", "value": -50 },
      {
        "id": "4",
        "type": "account",
        "label": "did:plc:abc123...",
        "value": 100
      }
    ],
    "prompt": "Show me posts about indie game development and pixel art. Skip NFT content.",
    "handle": "user.bsky.social",
    "password": "user-password",
    "access_jwt": "optional-jwt-token"
  }
  ```

  Returns:

  ```json
  {
    "message": "Feed deployed successfully",
    "uri": "at://did:plc:user123/app.bsky.feed.generator/my-custom-feed",
    "feed": {
      "id": "my-custom-feed",
      "name": "Indie Gaming Feed",
      "description": "A feed about indie games and pixel art",
      "uri": "at://did:plc:user123/app.bsky.feed.generator/my-custom-feed",
      "ruleset": { ... },
      "cache": [],
      "createdAt": "2026-03-24T12:34:56.789Z",
      "updatedAt": "2026-03-24T12:34:56.789Z"
    }
  }
  ```

  **How it works:**
  1. Converts tunings array to blueprint format expected by feed-manager
  2. Calls feed-manager API to create feed on Bluesky
  3. Stores feed metadata (including URI) in DynamoDB under user's account
  4. Returns feed URI and complete feed object to frontend

### Feeds

- `GET /feeds/{did}` - Get all feeds for an account
- `GET /feeds/{did}/{feedId}` - Get specific feed
- `POST /feeds/{did}/{feedId}/ruleset` - Update feed ruleset (blueprint)
  ```json
  { "ruleset": { "topic_preferences": [...], "profile_preferences": [...] } }
  ```
- `POST /feeds/{did}/{feedId}/cache` - Update feed cache (post URIs)
  ```json
  { "cache": ["at://did/post/1", "at://did/post/2"] }
  ```

### User Initialization

- `POST /feeds/{did}/initialize` - Initialize a new user with default feed

## Deployment

This is an AWS Lambda function designed to work with API Gateway.

1. Install dependencies: `npm install`
2. Set environment variables:
   - `OPENAI_API_KEY` - Required for feed ruleset generation
   - `PAPILLON_API_KEY` - Required for authenticating with feed-manager
   - `FEED_MANAGER_URL` - Feed manager endpoint (default: https://papillon-feed-manager-ftzwl3vpfq-uc.a.run.app/manage-feed)
3. Deploy via AWS Lambda console or SAM/CloudFormation
4. Configure API Gateway to proxy all requests to this Lambda
5. Ensure Lambda has DynamoDB read/write permissions for `papillon-feeds` and `papillon-subscriptions` tables

## Environment Variables

- `OPENAI_API_KEY` - OpenAI API key for AI-powered feed generation
- `PAPILLON_API_KEY` - API key for authenticating with feed-manager service
- `FEED_MANAGER_URL` - Feed manager endpoint URL (optional, defaults to production URL)

## No Authentication

This API does not implement authentication. Access control should be managed via API Gateway or IAM policies.
