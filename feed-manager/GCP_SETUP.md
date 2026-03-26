# Feed Manager - GCP to AWS DynamoDB Setup

## Overview

The feed-manager runs on **Google Cloud VM** but reads feed data from **AWS DynamoDB**. This requires cross-cloud authentication.

## Environment Setup on GCP VM

### 1. Install Dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file with the required credentials:

```bash
# Service configuration
HOSTNAME='feeds.papillon.fyi'

# API authentication
PAPILLON_API_KEY='your-papillon-api-key'

# AWS credentials (for DynamoDB access)
AWS_ACCESS_KEY_ID='your-aws-access-key'
AWS_SECRET_ACCESS_KEY='your-aws-secret-key'
AWS_REGION='us-east-1'

# AI services
OPENAI_API_KEY='your-openai-api-key'
```

### 3. AWS IAM Permissions

The AWS credentials need the following DynamoDB permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:Scan", "dynamodb:Query"],
      "Resource": ["arn:aws:dynamodb:us-east-1:*:table/papillon-feeds"]
    }
  ]
}
```

### 4. Run the Server

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

## Architecture

```
Frontend (localhost/papillon.fyi)
    ↓
Lambda (AWS) - feeds-api
    ↓ (writes to)
DynamoDB (AWS) - papillon-feeds table
    ↑ (reads from)
Feed Manager (GCP VM)
    ↓
Bluesky Network
```

## Data Flow

1. **Feed Creation**:
   - Frontend → Lambda → Feed Manager (creates on Bluesky)
   - Lambda stores metadata in DynamoDB

2. **Feed Serving**:
   - Feed Manager reads blueprints from DynamoDB
   - Generates feed content from Bluesky
   - Serves via `/xrpc/app.bsky.feed.getFeedSkeleton`

## Troubleshooting

### "Unable to locate credentials"

- Ensure `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are in `.env`
- Verify the `.env` file is in the feed-manager directory

### "No such table: papillon-feeds"

- The feed-manager now uses DynamoDB, not SQLite
- Delete old `feeds.db` file if it exists
- Verify DynamoDB table exists in AWS console

### CORS Errors

- Check that hostname matches in `.env` and feed creation
- Verify feed-manager is accessible at `feeds.papillon.fyi`
