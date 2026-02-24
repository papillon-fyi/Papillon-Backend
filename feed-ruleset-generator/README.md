# 🎛 Papillon Feed Ruleset Generator

A **FastAPI-based API** that generates personalized Bluesky feed configurations using GPT and semantic similarity. Takes natural language descriptions and produces ready-to-use feed blueprints with AI-selected accounts.

---

## 🗂️ Contents

- `main.py` – FastAPI app with `/api/health` and `/api/generate-feed-ruleset` endpoints
- `generate_feed_ruleset.py` – Core feed generation logic with LLM + embedding search
- `all-MiniLM-L6-v2.onnx` – Sentence transformer model for semantic similarity
- `requirements.txt` – Python dependencies
- `Dockerfile` – Container build instructions for Cloud Run
- `cloudbuild.yaml` – Cloud Build configuration for CI/CD

---

## 🔧 How It Works

1. **LLM Analysis**: User's natural language prompt is sent to GPT-5-nano which extracts:
   - Topic preferences (things to show)
   - Topic filters (things to avoid)
   - Ranking weights (relevance/popularity/recency balance)
   - Feed metadata (name, description)

2. **Semantic Search**: For each topic preference:
   - Searches Bluesky actors using `app.bsky.actor.searchActors`
   - Fetches 3 recent posts from each actor via `app.bsky.feed.getAuthorFeed`
   - Computes semantic similarity using ONNX sentence embeddings (all-MiniLM-L6-v2)
   - Ranks accounts by cosine similarity to topic query

3. **Account Selection**: Returns top 3 accounts per topic, deduplicates, keeps best scores

4. **Blueprint Generation**: Outputs a feed configuration with:
   - Profile preferences (DIDs + similarity scores)
   - Topic preferences with weights
   - Topic filters (blacklist)
   - Ranking weights (sum to 1.0)

---

## 🚀 Local Development

1. **Create a virtual environment:**

```bash
python3 -m venv venv
source venv/bin/activate
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

3. **Set environment variables:**

```bash
export API_KEY="your-secret-key"
export OPENAI_API_KEY="sk-your-openai-key"
```

4. **Run the API locally:**

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

5. **Test the generator directly:**

```bash
python3 generate_feed_ruleset.py
```

---

## 🏗️ Cloud Deployment (Google Cloud Run)

This service is designed for automatic deployment to Cloud Run via Cloud Build triggers.

### Prerequisites

- Google Cloud project with billing enabled
- Required APIs enabled:
  ```bash
  gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
  ```
- GitHub repository connected to Cloud Build via Developer Connect

### Cloud Build Trigger Setup

1. Go to **Cloud Build → Triggers → Create Trigger**
2. Configure the trigger:

| Field                           | Value                                         |
| ------------------------------- | --------------------------------------------- |
| **Name**                        | `deploy-feed-ruleset-generator`               |
| **Region**                      | `global`                                      |
| **Description**                 | Deploy feed ruleset generator on push to main |
| **Event**                       | `Push to a branch`                            |
| **Repository**                  | Your GitHub repo (via Developer Connect)      |
| **Branch**                      | `^main$`                                      |
| **Included files filter**       | `feed-ruleset-generator/**` (optional)        |
| **Configuration Type**          | `Cloud Build configuration file (yaml/json)`  |
| **Cloud Build config location** | `feed-ruleset-generator/cloudbuild.yaml`      |

### Setup: Create Repository and Grant Permissions

#### 1. Create Artifact Registry Repository

1. Go to: **Artifact Registry → Create Repository**
2. Configure:
   - **Name**: `feed-ruleset-generator` (must match name in cloudbuild.yaml)
   - **Format**: Docker
   - **Location type**: Region
   - **Region**: `us-central1` (or your preferred region)
3. Click **Create**

#### 2. Grant Cloud Build Service Account Access

1. Go to: **Cloud Build → Settings → Service account**
2. Copy the service account email (e.g., `123456789012@cloudbuild.gserviceaccount.com`)
3. Go to: **IAM & Admin → IAM**
4. Click **Grant Access**
5. Paste the Cloud Build service account email
6. Assign role: **Artifact Registry Writer**
7. Click **Save**

This gives the Cloud Build service account permission to push images to all Artifact Registry repositories in your project.

### Environment Variables (Substitution Variables)

In the trigger settings, go to **Advanced → Substitution variables** and add:

| Variable name     | Purpose                     | Example               |
| ----------------- | --------------------------- | --------------------- |
| `_API_KEY`        | API authentication          | `your-secret-api-key` |
| `_OPENAI_API_KEY` | GPT access for feed parsing | `sk-your-openai-key`  |

These are securely injected into Cloud Run via `cloudbuild.yaml`:

```yaml
--set-env-vars API_KEY=$_API_KEY,OPENAI_API_KEY=$_OPENAI_API_KEY
```

> ⚠️ **Never commit secrets to GitHub**. Use Cloud Build substitution variables.

---

## 🔌 API Endpoints

### `GET /api/health`

Health check endpoint.

**Headers:**

- `x-api-key: <API_KEY>`

**Response:**

```json
{
  "message": "Hello world!"
}
```

### `POST /api/generate-feed-ruleset`

Generate a feed blueprint from natural language.

**Headers:**

- `x-api-key: <API_KEY>`
- `Content-Type: application/json`

**Request Body:**

```json
{
  "query": "I want updates on AI research, especially papers about LLMs and neural architectures. Avoid crypto spam."
}
```

**Response:**

```json
{
  "status": "success",
  "ruleset": {
    "record_name": "ai-research-feed",
    "display_name": "AI Research Updates",
    "description": "Papers and discussions about LLMs and neural architectures",
    "blueprint": {
      "topic_preferences": [
        { "name": "AI research", "weight": 1.0 },
        { "name": "LLMs", "weight": 0.9 },
        { "name": "neural architectures", "weight": 0.8 }
      ],
      "topic_filters": [{ "name": "crypto", "weight": 0.5 }],
      "profile_preferences": [
        { "did": "did:plc:abc123...", "score": 0.847 },
        { "did": "did:plc:def456...", "score": 0.823 }
      ],
      "ranking_weights": {
        "relevance": 0.5,
        "popularity": 0.3,
        "recency": 0.2
      },
      "original_prompt": "I want updates on AI research...",
      "generated_at": "2026-02-23T12:34:56.789Z"
    }
  }
}
```

---

## 🧠 Technical Details

### Embedding Model

- **Model**: `all-MiniLM-L6-v2` (384-dimensional sentence embeddings)
- **Format**: ONNX for fast inference without GPU
- **Pooling**: Mean pooling with attention mask for proper sentence representations
- **Similarity**: Cosine similarity via normalized dot product

### Bluesky APIs Used

- `app.bsky.actor.searchActors` – Find accounts by search query
- `app.bsky.feed.getAuthorFeed` – Fetch recent posts from accounts

### Account Scoring

1. Fetch top 5 actors per topic from Bluesky search
2. Retrieve 3 most recent posts per actor
3. Concatenate posts and compute sentence embedding
4. Calculate cosine similarity between query embedding and account embedding
5. Keep top 3 accounts per topic
6. Deduplicate across topics, keeping highest score per account

### CORS Configuration

Allowed origins (configurable in `main.py`):

- `http://localhost:3000`
- `https://localhost:3000`
- `http://papillon.fyi`
- `https://papillon.fyi`

---

## 📦 Dependencies

Key Python packages:

- `fastapi` – Web framework
- `openai` – GPT API client
- `onnxruntime` – ONNX model inference
- `transformers` – Tokenizer for sentence embeddings
- `httpx` – Async HTTP client for Bluesky API
- `numpy` – Embedding operations

---

## 🔐 Security Notes

- API key required for all endpoints via `x-api-key` header
- No authentication required from Bluesky (uses public APIs)
- Secrets managed via Cloud Build substitution variables (not committed to repo)
- CORS restricted to known origins

---

## 📝 Example Usage

```python
import asyncio
from generate_feed_ruleset import generate_feed_ruleset

async def main():
    prompt = "Show me posts about indie game development and pixel art. Skip NFT content."
    result = await generate_feed_ruleset(query=prompt)
    print(result)

asyncio.run(main())
```

Output includes AI-selected accounts relevant to indie games and pixel art, with their similarity scores.
