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

## Deployment

This is an AWS Lambda function designed to work with API Gateway.

1. Install dependencies: `npm install`
2. Deploy via AWS Lambda console or SAM/CloudFormation
3. Configure API Gateway to proxy all requests to this Lambda
4. Ensure Lambda has DynamoDB read/write permissions for `papillon-accounts` table

## No Authentication

This API does not implement authentication. Access control should be managed via API Gateway or IAM policies.
