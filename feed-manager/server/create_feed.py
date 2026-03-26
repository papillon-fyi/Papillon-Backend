from atproto import Client, models
from server.algos import algos
from server.algos.feed import make_handler
import os
import time

def create_feed(handle, password, hostname, blueprint=None, access_jwt=None):
    """
    Create a feed on Bluesky.
    
    Blueprint should contain:
    - record_name: The rkey for the feed
    - display_name: Display name for the feed
    - description: Description of the feed
    - prompt: The original user prompt for the feed
    - topic_preferences, profile_preferences, topic_filters, profile_filters
    - ranking_weights
    """
    client = Client()
    client.login(handle, password)

    feed_did = "did:web:" + hostname.split("/")[0]
    print(f"[Feed Creation] Creating feed for DID: {feed_did}")

    # Extract metadata from blueprint
    record_name = blueprint.get('record_name', str(int(time.time() * 1000))) if blueprint else str(int(time.time() * 1000))
    display_name = blueprint.get('display_name', '') if blueprint else ''
    description = blueprint.get('description', '') if blueprint else ''
    prompt = blueprint.get('prompt', '') if blueprint else ''

    avatar_path = os.path.join(os.path.dirname(__file__), "avatar.png")
    avatar_blob = None
    if avatar_path and os.path.exists(avatar_path):
        with open(avatar_path, 'rb') as f:
            avatar_blob = client.upload_blob(f.read()).blob

    # Create or update record on Bluesky
    response = client.com.atproto.repo.put_record(
        models.ComAtprotoRepoPutRecord.Data(
            repo=client.me.did,
            collection=models.ids.AppBskyFeedGenerator,
            rkey=record_name,
            record=models.AppBskyFeedGenerator.Record(
                did=feed_did,
                display_name=display_name,
                description=description,
                avatar=avatar_blob,
                accepts_interactions=False,
                content_mode=None,
                created_at=client.get_current_time_iso(),
            )
        )
    )

    feed_uri = response.uri

    # Dynamically add handler to algos
    # The handler will fetch feed data (blueprint) from feeds-api when needed
    algos[feed_uri] = make_handler(feed_uri)
    
    print(f"[Feed Creation] Feed created successfully: {feed_uri}")
    print(f"[Feed Creation] Handler registered for feed")

    return feed_uri
