# Feed Manager Setup

## Architecture

```
Frontend → Feeds API (AWS Lambda) → DynamoDB
                ↑ HTTP requests
         Feed Manager (GCP)
```

Feed-manager makes HTTP requests to feeds-api, no direct AWS access needed!

## Setup

1. **Install dependencies:**

   ```bash
   pip3 install -r requirements.txt
   ```

2. **Configure `.env`:**

   ```bash
   HOSTNAME='feeds.papillon.fyi'
   PAPILLON_API_KEY='your-api-key'
   FEEDS_API_URL='https://m0xinwa8l4.execute-api.us-east-1.amazonaws.com/production'
   OPENAI_API_KEY='your-openai-key'
   ```

3. **Run server:**
   ```bash
   uvicorn server.app:app --host 0.0.0.0 --port 8000
   ```

## How It Works

- **Feed Creation:** Lambda calls feed-manager `/manage-feed` to create on Bluesky
- **Feed Serving:** Feed-manager calls feeds-api `/feeds/by-uri` to get blueprints
- **Storage:** All data in DynamoDB, accessed via feeds-api
