# 🦋 Papillon Feed Manager

A production-ready Bluesky feed generator service with intelligent caching, blueprint change detection, and personalized ranking. This service manages custom feed generators with persistent storage via AWS APIs, using Python, DynamoDB, and Uvicorn.

---

## Features

- **Cloud-native caching**: Feed and search cache stored in DynamoDB via REST APIs
- **Official Bluesky API integration**: Uses `app.bsky.feed.searchPosts` with JWT authentication for all searches
- **Blueprint change detection**: Automatic cache invalidation when feed sources or ranking weights change
- **Personalized ranking**: Configurable weights for relevance, popularity, and recency
- **ONNX-powered semantic search**: Fast embeddings using all-MiniLM-L6-v2 with batch encoding
- **Acronym detection**: GPT-4-powered acronym disambiguation for better search accuracy
- **Background regeneration**: Non-blocking feed updates for optimal performance
- **API-driven persistence**: Feeds stored in `papillon-feeds` DynamoDB table via AWS Lambda

For detailed information on acronym handling, see [ACRONYM_HANDLING.md](ACRONYM_HANDLING.md).

---

## Architecture Overview

The Papillon feed manager is part of a larger ecosystem:

```
┌─────────────────────────────────────────────────────────────┐
│  Papillon Ecosystem                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────────┐       ┌──────────────────────┐      │
│  │  Feed Ruleset     │       │  Subscriptions API   │      │
│  │  Generator (GCP)  │       │  (AWS Lambda)        │      │
│  │                   │       │                      │      │
│  │  - GPT-4o-mini    │       │  - Tier management   │      │
│  │  - ONNX encoding  │       │  - Stripe payments   │      │
│  │  - Cloud Run      │       │  - Feature gating    │      │
│  └───────────────────┘       └──────────────────────┘      │
│           │                            │                    │
│           │                            │                    │
│  ┌────────▼────────────────────────────▼──────────┐        │
│  │  Feed Manager (This Service)                   │        │
│  │                                                 │        │
│  │  - Bluesky searchPosts API                     │        │
│  │  - ONNX semantic search                        │        │
│  │  - Personalized ranking                        │        │
│  │  - Cache management                            │        │
│  └─────────────────────┬───────────────────────────┘       │
│                        │                                    │
│           ┌────────────▼──────────────┐                     │
│           │  Feeds API (AWS Lambda)  │                     │
│           │                           │                     │
│           │  - Feed CRUD operations   │                     │
│           │  - Cache storage          │                     │
│           │  - User initialization    │                     │
│           └───────────────────────────┘                     │
│                        │                                    │
│           ┌────────────▼──────────────┐                     │
│           │  DynamoDB                 │                     │
│           │                           │                     │
│           │  - papillon-feeds         │                     │
│           │  - papillon-subscriptions │                     │
│           └───────────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

**API Endpoints:**

- **Feeds API**: `https://m0xinwa8l4.execute-api.us-east-1.amazonaws.com/production`
- **Subscriptions API**: `https://d1abpjglrf.execute-api.us-east-1.amazonaws.com/production`
- **Feed Ruleset Generator**: Google Cloud Run (configured separately)

All services authenticate using the same `PAPILLON_API_KEY`.

---

## VM & Network Setup

To run your Bluesky feed manager, you'll need a small Linux VM with a static external IP, DNS pointing to it, and firewall rules allowing web traffic. Below is a recommended setup based on a working configuration deployed on Google Cloud Platform (GCP), though the same approach works on AWS, Azure, DigitalOcean, etc.

### Create a VM Instance

Choose any cloud provider and create a lightweight virtual machine.

**Recommended VM configuration (example using GCP):**

| Setting                           | Recommended Value                                                     |
| --------------------------------- | --------------------------------------------------------------------- |
| **Name**                          | `papillon-feed-manager`                                               |
| **Region / Zone**                 | e.g., `us-central1-f`                                                 |
| **Machine Type**                  | `e2-micro` (2 vCPUs, 1 GB RAM) — works well and is free-tier eligible |
| **Boot Disk**                     | Ubuntu **22.04** LTS or Ubuntu **24.04** LTS                          |
| **Disk Size**                     | ~10 GB                                                                |
| **External IP**                   | Static or Ephemeral (Static preferred)                                |
| **Firewall (during VM creation)** | ✔ Allow HTTP, ✔ Allow HTTPS                                           |

Once created, your VM will receive:

- An **internal IP** (e.g., `10.128.0.3`)
- An **external IPv4** — **this one is auto-assigned and _ephemeral_** (e.g., `203.0.113.45`)

The ephemeral external IP **can change at any time** (e.g., when the VM stops/starts), so it should **not** be used for DNS.

### Reserve a Static External IP

To ensure your VM keeps the same public address, reserve a **static external IP** and attach it to the instance. This static IP will replace the ephemeral one.

Example (placeholder):

```
External IP (static): 35.67.414.20
```

### Configure DNS

In your DNS provider (e.g., GoDaddy, Cloudflare, Namecheap), create an **A record** that points your feed domain to your VM's external IP.

Example DNS record:

| Type | Name    | Data (IP)        | Meaning                                |
| ---- | ------- | ---------------- | -------------------------------------- |
| A    | `feeds` | **35.67.414.20** | `feeds.papillon.fyi` → feed manager VM |

This domain will be used as your `HOSTNAME` and for your SSL certificate.

### Firewall Rules

Your VM must receive inbound traffic on these ports:

| Purpose                    | Port |
| -------------------------- | ---- |
| HTTP (Caddy)               | 80   |
| HTTPS (Caddy)              | 443  |
| App Server / API (Uvicorn) | 8000 |

Create an ingress firewall rule:

```
Name: allow-web
Direction: Ingress
Source IP Range: 0.0.0.0/0
Allowed Protocols: tcp:80, tcp:443, tcp:8000
Target: All instances (or apply a network tag)
```

---

## Installation

### 1. Install System Dependencies

SSH into your VM and run:

```bash
sudo apt update
sudo apt install -y \
    uvicorn \
    python3-pip \
    debian-keyring \
    debian-archive-keyring \
    apt-transport-https \
    curl \
    sqlite3 \
    htop \
    iotop \
```

_NOTE: This takes approximately 2-5 minutes to complete._

### 2. Install Python Dependencies

```bash
sudo pip3 install --upgrade --force-reinstall --ignore-installed \
    python-dotenv \
    atproto \
    peewee \
    typing-extensions \
    numpy \
    onnxruntime \
    transformers \
    fastapi \
    uvicorn \
    openai \
    --break-system-packages
```

_NOTE: This takes approximately 2-5 minutes to complete._

### 3. Clone Repository

```bash
git clone https://github.com/papillon-fyi/Papillon-Backend.git
cd Papillon-Backend/feed-manager
```

### 4. Configure Environment Variables

1. Copy the example environment file:

```bash
cp .env.example .env
nano .env
```

2. Set the required variables:

```env
# Service configuration
HOSTNAME='feeds.example.com'

# API authentication - shared across all Papillon services
PAPILLON_API_KEY='your-secure-api-key-here'

# AI services
OPENAI_API_KEY='your-openai-api-key'
```

Save and exit when done.

---

## Install and Configure Caddy

Caddy provides automatic HTTPS and reverse-proxies requests to the backend service on port 8000.

### Step 1: Install Caddy

On your VM:

```bash
cd ~
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list

sudo apt update
sudo apt install -y caddy
```

This will:

- Install Caddy as a **systemd service**
- Enable automatic startup on boot
- Provide HTTPS via Let's Encrypt automatically

Check installation:

```bash
caddy version
```

_NOTE: Installation takes approximately 10-15 minutes. Errors related to `/var/lib/apt/lists/lock` are normal and can be ignored._

### Step 2: Configure Caddyfile

1. Open the main Caddyfile:

```bash
sudo nano /etc/caddy/Caddyfile
```

2. Replace the contents with your configuration (replace `feeds.example.com` with your actual domain):

```caddy
feeds.example.com {
    encode gzip

    # Send everything to FastAPI
    reverse_proxy 127.0.0.1:8000
}
```

This tells Caddy to:

- Serve your API at `https://feeds.example.com/...`
- Automatically handle HTTPS
- Forward requests to your backend on port 8000

### Step 3: Start and Enable Caddy

1. **Validate your Caddyfile**:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
```

2. **Start Caddy**:

```bash
sudo systemctl start caddy
```

3. **Enable automatic start on boot**:

```bash
sudo systemctl enable caddy
```

4. **Check status**:

```bash
sudo systemctl status caddy
sudo journalctl -u caddy -f
```

Caddy will automatically fetch SSL certificates for your domain (make sure your DNS A record points to your VM).

**Troubleshooting**: If `curl https://feeds.example.com` fails with connection errors, Caddy may not be properly bound to ports 80/443. Run `sudo systemctl daemon-reload` and `sudo systemctl restart caddy` to ensure Caddy picks up the configuration, obtains the TLS certificate, and starts listening on the correct ports.

---

## Run the Service

### Start the Server

Make the server script executable and start it:

```bash
chmod +x run_server.sh
./run_server.sh start
```

### Check Status

```bash
./run_server.sh status
```

### Stop the Server

```bash
./run_server.sh stop
```

### Run in Foreground (for debugging)

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

_NOTE: It takes about 2-5 minutes for the service to fully start. If running in background fails, start it in foreground first, then restart in background once initialized._

### Test Your Deployment

Check for signs of life:

```bash
curl https://feeds.example.com/xrpc/app.bsky.feed.describeFeedGenerator
```

Expected response:

```json
{
  "encoding": "application/json",
  "body": {
    "did": "did:web:feeds.example.com",
    "feeds": []
  }
}
```

---

## Local Development

### Prerequisites

- Python 3.11+
- Access to Papillon AWS APIs (feeds-api and subscriptions-api)
- Bluesky account with access JWT
- OpenAI API key for acronym detection
- ONNX model file (`all-MiniLM-L6-v2.onnx`)

### Local Setup

1. Copy the example environment file:

```bash
cp .env.example .env
nano .env
```

2. Set the required variables:

```env
# Service configuration
HOSTNAME='feed.papillon.fyi'

# API authentication - shared across all Papillon services
PAPILLON_API_KEY='your-secure-api-key-here'

# AI services
OPENAI_API_KEY='your-openai-api-key'
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `httpx` - Async HTTP client for API calls
- `numpy` - Numerical operations
- `onnxruntime` - ONNX model inference
- `transformers` - Tokenization for embeddings
- `peewee` - Database ORM (local models)
- `openai` - GPT-4 for acronym detection
- `python-dotenv` - Environment variable management

3. Configure environment:

```bash
cp .env.example .env
nano .env
```

4. Run locally:

```bash
uvicorn server.app:app --reload --host 127.0.0.1 --port 8000
```

### Health Check

```bash
curl http://localhost:8000/
```

Expected response: ASCII art logo and service information.

---

## How It Works

### Feed Generation Pipeline

1. **User Request**: Client requests feed skeleton via `/xrpc/app.bsky.feed.getFeedSkeleton`
2. **Cache Check**: System checks DynamoDB cache via Feeds API
3. **Cache Validation**:
   - Checks if blueprint hash matches (sources/weights unchanged)
   - Verifies oldest post is within 48 hours
   - Returns cached feed if valid
4. **Feed Building** (if cache invalid):
   - Fetches feed sources from local database
   - Performs Bluesky API searches with JWT authentication
   - Applies acronym expansion for better search accuracy
   - Fetches full post details concurrently
   - Filters by blacklists and recency
   - Ranks by composite score (relevance + popularity + recency)
   - Stores result in DynamoDB via Feeds API
5. **Response**: Returns paginated feed skeleton to client

### Search Strategy

The service uses intelligent search routing based on source type:

**For Acronyms** (detected via GPT-4):

- Uses ONLY semantic vector search with expanded context
- Example: "CHI" → "CHI conference human-computer interaction HCI research"
- Prevents false matches with common words

**For Regular Terms**:

- Uses BOTH text search AND semantic vector search
- Text search: Direct keyword matching via Bluesky API
- Vector search: ONNX embeddings with cosine similarity
- Results merged and deduplicated

**For Profile Preferences**:

- Direct author feed fetch via `app.bsky.feed.getAuthorFeed`
- No search API calls needed

### Ranking Algorithm

Posts are scored using three weighted factors:

**1. Relevance Score (0-1)**:

- Profile match: +1.0 if from preferred author
- Topic match: Weight-based scoring for keyword presence
- Capped at 1.0

**2. Popularity Score (0-1)**:

- Engagement: likes + (replies × 2) + (reposts × 3) + (quotes × 2)
- Log scaling: `min(log1p(engagement) / 5.0, 1.0)`
- Prevents viral posts from dominating

**3. Recency Score (0-1)**:

- Exponential decay: `exp(-age / (48h / 3))`
- Half-life: ~16 hours
- Ensures fresh content surfaces

**Final Score**:

```
score = (relevance × w_rel) + (popularity × w_pop) + (recency × w_rec)
```

Default weights: 50% relevance, 30% popularity, 20% recency (configurable per feed)

### Cache Management

**Cache Storage**: DynamoDB via Feeds API

- Endpoint: `POST /feeds/{did}/{feedId}/cache`
- Data includes: feed skeleton, timestamp, blueprint hash, oldest post timestamp

**Cache Invalidation Triggers**:

- Blueprint changes (sources or ranking weights modified)
- Oldest post exceeds 48 hours
- Manual cache clear via utility script

**Cache Refresh Strategy**:

- Immediate: Returns stale cache while rebuilding if >5min old
- Background: Rebuilds feed asynchronously
- No cold starts: Users always get instant response

### Acronym Detection

The service uses GPT-4o-mini to detect and expand acronyms:

**Process**:

1. Analyze topic names in context of user's feed intent
2. Identify potential acronyms (short uppercase terms)
3. Expand with semantic context
4. Store expansion in feed source metadata

**Example**:

- User intent: "Latest research in human-computer interaction"
- Topic: "CHI"
- Detection: Acronym detected
- Expansion: "CHI conference human-computer interaction HCI research"
- Search: Uses only semantic vector search with expanded query

See [ACRONYM_HANDLING.md](ACRONYM_HANDLING.md) for detailed implementation.

---

## API Integration

### Feeds API Calls

The service makes authenticated requests to the Feeds API:

**Get Feed Cache**:

```http
GET /feeds/{did}/{feedId}
x-api-key: {PAPILLON_API_KEY}
```

**Update Feed Cache**:

```http
POST /feeds/{did}/{feedId}/cache
x-api-key: {PAPILLON_API_KEY}
Content-Type: application/json

{
  "cache": {
    "feed": { ... },
    "timestamp": 1234567890,
    "oldest_timestamp": 1234567800,
    "blueprint_hash": "abc123..."
  }
}
```

### Bluesky API Authentication

All Bluesky API calls require JWT authentication:

**Storage**: `access_jwt` stored in Feed model (local database)

**Usage**: Passed as Bearer token to Bluesky endpoints:

- `app.bsky.feed.searchPosts` (text and semantic search)
- `app.bsky.feed.getAuthorFeed` (profile preferences)
- `app.bsky.feed.getPosts` (full post details)

**Refresh**: Managed externally by client applications

---

## Performance Optimization

### ONNX Batch Encoding

Semantic searches use batch encoding for 3-5x speedup:

**Before** (sequential):

```python
for text in texts:
    embedding = encode_onnx(text)  # 15-20 separate calls
```

**After** (batch):

```python
embeddings = encode_onnx(all_texts)  # Single inference call
```

### Concurrent Fetching

All external API calls use asyncio with semaphore limits:

```python
sem = asyncio.Semaphore(10)  # Max 10 concurrent requests
tasks = [fetch_with_sem(uri) for uri in uris]
results = await asyncio.gather(*tasks)
```

Prevents rate limiting while maximizing throughput.

### Intelligent Collection Scaling

Collection size adapts to `MAX_PER_AUTHOR` setting:

```python
multiplier = max(2, 10 // MAX_PER_AUTHOR)
target_collected = FEED_LIMIT * multiplier
```

Stricter author limits = larger initial collection to ensure feed fills.

---

## Configuration

### Feed Model Fields

Each feed in the local database contains:

- `uri`: AT Protocol URI (e.g., `at://did:plc:abc/app.bsky.feed.generator/my-feed`)
- `access_jwt`: Bluesky JWT for authenticated API calls
- `ranking_weights`: JSON with relevance/popularity/recency weights
- `created_at`, `updated_at`: Timestamps

### Feed Source Types

Sources define what content appears in a feed:

- `topic_preference`: Keyword/semantic search (weight-based priority)
  - Has `is_acronym` flag and optional `context` for expansion
- `profile_preference`: Specific author DID to follow
- `topic_filter`: Banned keywords (blacklist)
- `profile_filter`: Blocked author DIDs (blacklist)

### Tunable Constants

In `server/algos/feed.py`:

```python
SEARCH_CACHE_TTL = 30        # Search cache lifetime (seconds)
FEED_CACHE_TTL = 300         # Feed cache lifetime (seconds)
RESPONSE_LIMIT = 10          # Posts per API request
FEED_LIMIT = 100            # Total posts per feed
MAX_PER_AUTHOR = 10         # Max posts from single author
MAX_AGE_SECONDS = 172800    # 48 hours - max post age
```

---

## Configuration

### Feed Model Fields

Each feed in the local database contains:

- `uri`: AT Protocol URI (e.g., `at://did:plc:abc/app.bsky.feed.generator/my-feed`)
- `access_jwt`: Bluesky JWT for authenticated API calls
- `ranking_weights`: JSON with relevance/popularity/recency weights
- `created_at`, `updated_at`: Timestamps

### Feed Source Types

Sources define what content appears in a feed:

- `topic_preference`: Keyword/semantic search (weight-based priority)
  - Has `is_acronym` flag and optional `context` for expansion
- `profile_preference`: Specific author DID to follow
- `topic_filter`: Banned keywords (blacklist)
- `profile_filter`: Blocked author DIDs (blacklist)

### Tunable Constants

In `server/algos/feed.py`:

```python
SEARCH_CACHE_TTL = 30        # Search cache lifetime (seconds)
FEED_CACHE_TTL = 300         # Feed cache lifetime (seconds)
RESPONSE_LIMIT = 10          # Posts per API request
FEED_LIMIT = 100            # Total posts per feed
MAX_PER_AUTHOR = 10         # Max posts from single author
MAX_AGE_SECONDS = 172800    # 48 hours - max post age
```

### Cache Management

Cache is now stored in DynamoDB via the Feeds API. To clear cache:

1. **Via API**: `DELETE /feeds/{did}/{feedId}/cache` (not yet implemented)
2. **Via DynamoDB Console**: Manually update the cache field in `papillon-feeds` table
3. **Automatic**: Cache invalidates when blueprint hash changes or posts exceed 48 hours

---

## Deployment

### Production Setup (VM with Caddy)

1. **Reserve Static IP**: Ensure stable external address for DNS
2. **Configure DNS**: Point feed subdomain to VM IP
3. **Install Caddy**: Automatic HTTPS with Let's Encrypt
4. **Caddyfile Configuration**:

```caddy
feed.papillon.fyi {
    encode gzip
    reverse_proxy 127.0.0.1:8000
}
```

5. **Environment Variables**: Set `HOSTNAME`, `PAPILLON_API_KEY`, `OPENAI_API_KEY`
6. **Start Service**: `./run_server.sh start`
7. **Enable Systemd**: `sudo systemctl enable caddy`

### Firewall Rules

Required ports:

- `80` (HTTP - Caddy redirects to HTTPS)
- `443` (HTTPS - Caddy with SSL)
- `8000` (App server - internal only if using Caddy)

### Health Checks

**Service Status**:

```bash
./run_server.sh status
```

**API Test**:

```bash
curl https://feed.papillon.fyi/xrpc/app.bsky.feed.describeFeedGenerator
```

Expected response:

```json
{
  "encoding": "application/json",
  "body": {
    "did": "did:web:feed.papillon.fyi",
    "feeds": [...]
  }
}
```

---

## Development

### Local Testing

```bash
# Run with auto-reload
uvicorn server.app:app --reload --host 127.0.0.1 --port 8000

# View logs
tail -f logs/feed-manager.log
```

### Adding New Feed Sources

1. Create feed via Feeds API or external client
2. Service automatically picks up new feeds on restart
3. Or dynamically register: `algos[feed_uri] = make_handler(feed_uri)`

### Debugging

Enable debug logging in `.env`:

```env
LOG_LEVEL=DEBUG
```

Common issues:

- **Missing JWT**: Check `access_jwt` field in Feed model
- **Cache misses**: Verify Feeds API connectivity and API key
- **Search failures**: Confirm Bluesky API authentication works
- **Slow performance**: Check ONNX model path and batch encoding

---

## API Endpoints (Bluesky Protocol)

### Describe Feed Generator

```http
GET /xrpc/app.bsky.feed.describeFeedGenerator
```

Returns service DID and list of available feeds.

### Get Feed Skeleton

```http
GET /xrpc/app.bsky.feed.getFeedSkeleton
  ?feed={feed_uri}
  &cursor={offset}
  &limit={count}
```

Returns paginated list of post URIs matching feed criteria.

### Well-Known DID

```http
GET /.well-known/did.json
```

Returns DID document for service verification.

---

## Contributing

When making changes:

1. **Update migrations**: If modifying database schema
2. **Clear cache**: After ranking weight changes
3. **Test acronyms**: Verify GPT-4 detection works correctly
4. **Check API calls**: Ensure proper JWT authentication
5. **Monitor performance**: Batch operations where possible

---

## License

See [LICENSE](LICENSE) for details.

---

## Support

For issues or questions:

- Check logs: `./run_server.sh logs`
- Review [ACRONYM_HANDLING.md](ACRONYM_HANDLING.md) for search behavior
- Verify API connectivity with health checks
- Ensure all environment variables are set correctly
