"""MongoEngine documents for the Focus Score Computation Engine (paper FR03)."""
from mongoengine import Document, fields


class FESScore(Document):
    """One row per session: FES and its five sub-metrics (paper Eq. 1)."""

    session = fields.StringField(required=True, unique=True)
    student = fields.StringField(required=True)
    tcr = fields.FloatField()
    sci = fields.FloatField()
    dfet = fields.FloatField()
    qap = fields.FloatField()
    lrds = fields.FloatField()
    fes = fields.FloatField(min_value=0, max_value=1)
    weights = fields.DictField()
    computed_at = fields.DateTimeField(required=True)


class FESWeights(Document):
    """Per-student Eq. 2 weight vector; student=None denotes the
    population-level cold-start vector."""

    student = fields.StringField()
    weights = fields.DictField(required=True)  # {"tcr": w1, ..., "lrds": w5}
    n_sessions = fields.IntField(required=True)
    n_graded_outcomes = fields.IntField()
    computed_at = fields.DateTimeField(required=True)

    meta = {
        "indexes": ["student"],
        "allow_inheritance": False,
    }
