"""MongoEngine documents for the Behavioural Data Collector (paper FR02).

The collector is the ingestion half of the behavioural pipeline: sessions wrap
streams of raw interaction events emitted by the frontend tracking SDK.

Collection coexistence: seeded data (source="simulator"/"oulad") and live
collector data (source="collector") share the `sessions`/`events` collections,
distinguished by `source`.
"""
from mongoengine import Document, fields


class BehaviourSession(Document):
    student = fields.StringField(required=True)
    status = fields.StringField(choices=("active", "completed"), default="active")
    started_at = fields.DateTimeField(required=True)
    ended_at = fields.DateTimeField()
    duration_seconds = fields.IntField()
    # session-end aggregates used by the FES engine
    interaction_count = fields.IntField(default=0)
    tasks_started = fields.IntField(default=0)
    tasks_completed = fields.IntField(default=0)
    # fields materialised by collector.services for FES (mirror simulator schema)
    duration_minutes = fields.FloatField()
    date = fields.StringField()
    login_minute_of_day = fields.IntField()
    resource_visits = fields.ListField(fields.DictField())
    quiz_items = fields.IntField(default=0)
    quiz_items_correct = fields.IntField(default=0)
    quiz_reattempts = fields.IntField(default=0)
    assessment_score = fields.FloatField()
    source = fields.StringField(default="collector")

    meta = {"collection": "sessions", "allow_inheritance": False}


class BehaviourEvent(Document):
    """Raw interaction event (page_view, resource_open, resource_close,
    resource_switch, idle_start, idle_end, task_start, task_complete,
    quiz_attempt, heartbeat)."""

    session = fields.StringField(required=True)
    student = fields.StringField(required=True)
    type = fields.StringField(required=True)
    resource_id = fields.StringField()
    metadata = fields.DictField()
    timestamp = fields.DateTimeField(required=True)

    meta = {"collection": "events", "allow_inheritance": False}
