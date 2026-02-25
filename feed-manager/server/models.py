from peewee import Model, SqliteDatabase, TextField, ForeignKeyField, IntegerField, FloatField

db = SqliteDatabase('feeds.db')

class Feed(Model):
    uri = TextField(unique=True)
    handle = TextField()
    record_name = TextField()
    display_name = TextField()
    description = TextField(null=True)
    avatar_path = TextField(null=True)
    ranking_weights = TextField(null=True)  # JSON string of ranking weights
    blueprint_hash = TextField(null=True)  # Hash of sources + ranking_weights to detect blueprint changes
    access_jwt = TextField(null=True)  # User's access JWT for authenticated Bluesky API requests

    class Meta:
        database = db


class FeedSource(Model):
    feed = ForeignKeyField(Feed, backref='sources', on_delete='CASCADE')
    source_type = TextField()   # 'profile_preference', 'topic_preference', 'profile_filter', 'topic_filter'
    identifier = TextField()    # e.g., 'did:plc:example.bsky.social' or 'sports'
    weight = FloatField(default=0.5)  # numerical weight for this source
    is_acronym = IntegerField(default=0)  # 1 if identifier is an acronym (use vector-only search)
    context = TextField(null=True)  # Optional context for disambiguation (e.g., original prompt)

    class Meta:
        database = db
        indexes = (
            (('feed', 'source_type', 'identifier'), True),
        )

class FeedCache(Model):
    feed_uri = TextField(unique=True)
    response_json = TextField()  # JSON string of {"cursor":..., "feed":[...]}
    timestamp = IntegerField()   # UNIX timestamp
    oldest_timestamp = IntegerField(null=True)  # UNIX timestamp of oldest post in feed
    blueprint_hash = TextField(null=True)  # Hash of blueprint that generated this cache

    class Meta:
        database = db


class SearchCache(Model):
    query = TextField()
    search_type = TextField()  # 'vector' or 'text'
    results_json = TextField()  # JSON list of {"repo":..., "rkey":...}
    timestamp = IntegerField()  # UNIX timestamp

    class Meta:
        database = db
        indexes = (
            (('query', 'search_type'), True),
        )