from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import os

from generate_feed_ruleset import generate_feed_ruleset
from fastapi.middleware.cors import CORSMiddleware

# App setup
app = FastAPI()

# CORS configuration
allowed_origins = [ # Set your allowed origins here
    "http://localhost:3000",
    "https://localhost:3000",

    "http://papillon.fyi",
    "https://papillon.fyi"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],   # or ["GET", "POST", "OPTIONS"]
    allow_headers=["*"],
)

API_KEY = os.getenv("API_KEY")

class IntentRequest(BaseModel):
    query: str

@app.get("/api/health")
async def hello(request: Request):
    key = request.headers.get("x-api-key")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return {"message": "Hello world!"}


@app.post("/api/generate-feed-ruleset")
async def generate_ruleset(request: Request, body: IntentRequest):
    key = request.headers.get("x-api-key")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    try:
        ruleset = await generate_feed_ruleset(body.query)
        return {"status": "success", "ruleset": ruleset}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
