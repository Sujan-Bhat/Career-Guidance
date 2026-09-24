"""MongoEngine documents for career pathways and the prediction outputs (paper FR08)."""
from mongoengine import Document, EmbeddedDocument, fields


class SkillPrerequisite(EmbeddedDocument):
    skill = fields.StringField(required=True)
    min_level = fields.IntField(min_value=1, max_value=5)


class CareerPathway(Document):
    """Career category node of the knowledge graph (paper Sec. V-B Stage 1).
    Seeded from data/knowledge_graph/careers_seed.json by data/seeds/seed_mongo.py."""

    external_id = fields.StringField(required=True, unique=True)
    name = fields.StringField(required=True)
    category = fields.StringField(required=True)
    description = fields.StringField()
    prerequisites = fields.ListField(fields.EmbeddedDocumentField(SkillPrerequisite))
    typical_courses = fields.ListField(fields.StringField())


class CareerPrediction(Document):
    """Confidence-ranked probability distribution over career categories
    plus top contributing profile features (transparency, paper Sec. V-D)."""

    student = fields.StringField(required=True)
    distribution = fields.ListField(fields.DictField())  # [{"pathway": ..., "probability": ...}]
    top_features = fields.ListField(fields.DictField())  # [{"feature": ..., "importance": ...}]
    model_version = fields.StringField()
    predicted_at = fields.DateTimeField(required=True)
