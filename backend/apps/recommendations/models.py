"""MongoEngine documents for issued recommendations (paper FR05, FR11)."""
from mongoengine import Document, fields


class Recommendation(Document):
    """A career-pathway/course recommendation issued to a student.

    Per-stage provenance (`stage1_eligible`, `stage2_cf_score`, `stage3_fm_score`)
    is stored so the LLM explanation layer (NFR07) can cite why the item ranked.
    """

    student = fields.StringField(required=True)
    item_type = fields.StringField(choices=("pathway", "course"), default="pathway")
    item_id = fields.StringField(required=True)
    stage1_eligible = fields.BooleanField()
    stage2_cf_score = fields.FloatField()
    stage3_fm_score = fields.FloatField()
    contributing_features = fields.ListField(fields.DictField())
    explanation = fields.StringField()
    decision = fields.StringField(choices=("pending", "accepted", "rejected"), default="pending")
    created_at = fields.DateTimeField(required=True)
