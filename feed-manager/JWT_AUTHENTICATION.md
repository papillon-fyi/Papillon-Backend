# JWT Authentication Migration

## Overview

Updated the feed-manager to accept and use Bluesky `accessJwt` tokens for authenticated API searches, replacing the deprecated custom API.

## Changes Made

### 1. Database Schema (`models.py`)

- Added `access_jwt` field to `Feed` model to store user's JWT token
- This allows authenticated Bluesky API requests when building feeds

### 2. API Endpoint (`app.py`)

- Added `"accessJwt"` to `allowed_keys` list
- JWT is now accepted in POST requests to `/manage-feed` endpoint

### 3. Feed Creation (`create_feed.py`)

- Updated function signature to accept `accessJwt` parameter
- JWT is stored in Feed record during creation/update
- Added `access_jwt` to the fields that get updated when feed already exists

### 4. Search Functions (`algos/feed.py`)

#### Removed

- `CUSTOM_API_URL` environment variable dependency
- Custom vector search endpoint (`/vector/search/posts`)
- Custom text search endpoint (`/search/posts`)

#### Updated

- `search_vector()`: Now uses Bluesky's `app.bsky.feed.searchPosts` API with JWT authentication
- `search_text()`: Now uses Bluesky's `app.bsky.feed.searchPosts` API with JWT authentication
- Both functions accept `access_jwt` parameter (defaults to None)
- Both functions add `Authorization: Bearer {accessJwt}` header to requests

#### Feed Building

- `build_feed()` now retrieves `access_jwt` from Feed record
- Passes JWT to all `search_text()` and `search_vector()` calls

### 5. Migration Script

Created `migrate_add_access_jwt.py`:

- Adds `access_jwt` column to existing Feed table
- Safe to run multiple times (checks if column exists)
- Run with: `python migrate_add_access_jwt.py`

## API Changes

### Request Format

```json
{
  "handle": "user.bsky.social",
  "password": "app-password",
  "hostname": "https://bsky.social",
  "record_name": "my-feed",
  "display_name": "My Feed",
  "description": "Feed description",
  "accessJwt": "eyJ0eXAiOiJhdCt...",  // NEW
  "original_prompt": "I want posts about...",
  "blueprint": {
    "profile_preferences": [...],
    "topic_preferences": [...]
  }
}
```

### Bluesky API Used

- **Endpoint**: `https://bsky.social/xrpc/app.bsky.feed.searchPosts`
- **Method**: GET
- **Headers**: `Authorization: Bearer {accessJwt}`
- **Params**: `q` (query string), `limit` (number of results)
- **Response**: Returns posts array with post objects

## Benefits

1. ✅ No longer depends on custom API infrastructure
2. ✅ Uses official Bluesky APIs for better reliability
3. ✅ Authenticated searches provide better results
4. ✅ JWT stored per-feed for automatic use during feed builds
5. ✅ Maintains caching for performance

## Migration Steps

1. Run migration script: `python feed-manager/migrate_add_access_jwt.py`
2. Update frontend to include `accessJwt` in feed creation requests
3. Remove `CUSTOM_API_URL` from environment variables (no longer needed)

## Notes

- JWTs expire periodically - frontend should refresh and update feeds with new tokens
- Search functions gracefully handle missing JWT (return empty results with warning)
- Cache still works as before (30s for search results, 5min for feeds)
