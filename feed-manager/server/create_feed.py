from atproto import Client, models
from server.models import Feed, FeedSource
from server.algos import algos
from server.algos.feed import make_handler, detect_and_expand_acronyms
import os
import json

def create_feed(handle, password, hostname, record_name, display_name="", description="",
                avatar_path=os.path.join(os.path.dirname(__file__), "avatar.png"),
                blueprint=None, original_prompt=None, access_jwt=None):
    client = Client()
    client.login(handle, password)

    feed_did = "did:web:" + hostname.split("/")[0]
    print(f"[Feed Creation] Creating feed for DID: {feed_did}")

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

    # Extract ranking weights from blueprint
    ranking_weights_json = None
    if blueprint and "ranking_weights" in blueprint:
        ranking_weights_json = json.dumps(blueprint["ranking_weights"])

    # Save feed metadata locally
    data = {
        "handle": handle,
        "record_name": record_name,
        "display_name": display_name,
        "description": description,
        "avatar_path": avatar_path,
        "ranking_weights": ranking_weights_json,
        "access_jwt": access_jwt,
    }

    feed, created = Feed.get_or_create(
        uri=feed_uri,
        defaults=data
    )

    if not created:
        updated = False
        for field in ["handle", "record_name", "display_name", "description", "avatar_path", "ranking_weights", "access_jwt"]:
            value = data.get(field)
            if value and getattr(feed, field) != value:
                setattr(feed, field, value)
                updated = True
        if updated:
            feed.save()

    # Feed blueprint processing
    if blueprint:
        # Delete old sources for this feed
        FeedSource.delete().where(FeedSource.feed == feed).execute()

        # Detect and expand acronyms in topic preferences
        topic_preferences = blueprint.get('topic_preferences', [])
        if original_prompt:
            topic_preferences = detect_and_expand_acronyms(topic_preferences, original_prompt)

        # Topic Preferences (positive)
        for topic in topic_preferences:
            FeedSource.create(
                feed=feed,
                source_type='topic_preference',
                identifier=topic['name'],
                weight=topic.get('weight', 0.5),
                is_acronym=topic.get('is_acronym', 0),
                context=topic.get('context')
            )
        
        # Profile Preferences (positive)
        for profile in blueprint.get('profile_preferences', []):
            FeedSource.create(
                feed=feed,
                source_type='profile_preference',
                identifier=profile['did'],
                weight=profile.get('weight', 0.5)
            )

        # Topic Filters (negative)
        for topic in blueprint.get('topic_filters', []):
            FeedSource.create(
                feed=feed,
                source_type='topic_filter',
                identifier=topic['name'],
                weight=topic.get('weight', 0.5)
            )
        
        # Profile Filters (negative)
        for profile in blueprint.get('profile_filters', []):
            FeedSource.create(
                feed=feed,
                source_type='profile_filter',
                identifier=profile['did'],
                weight=profile.get('weight', 0.5)
            )

    # Dynamically add handler to algos
    algos[feed_uri] = make_handler(feed_uri)

    # Warm the cache of dynamically collected posts immediately
    try:
        handler = algos[feed_uri]
        import asyncio

        # Trigger handler in the background
        asyncio.get_event_loop().create_task(handler())
        print(f"[Cache Warm] Started background warm for {feed_uri}")

    except Exception as e:
        print(f"[Cache Warm Error] Could not warm cache for {feed_uri}: {e}")

    return feed_uri
