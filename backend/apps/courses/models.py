"""MongoEngine documents for the course catalogue, resources, tasks, quizzes (paper FR04)."""
from mongoengine import Document, fields


class Course(Document):
    code = fields.StringField(required=True, unique=True)
    title = fields.StringField(required=True)
    difficulty = fields.IntField(min_value=1, max_value=5)
    skill_tags = fields.ListField(fields.StringField())
    pathway = fields.StringField()
    description = fields.StringField()


class Resource(Document):
    """Learning resource; `type` drives the LRDS dwell-time threshold."""

    course = fields.StringField(required=True)
    title = fields.StringField(required=True)
    type = fields.StringField(choices=("video", "article", "exercise", "interactive"))


class Task(Document):
    course = fields.StringField(required=True)
    title = fields.StringField(required=True)
    description = fields.StringField()


class Quiz(Document):
    course = fields.StringField()
    skill = fields.StringField(required=True)
    title = fields.StringField(required=True)
    questions = fields.ListField(fields.DictField())


class QuizAttempt(Document):
    """Records every attempt; the QAP sub-metric needs incorrect-item re-attempts."""

    quiz = fields.StringField(required=True)
    student = fields.StringField(required=True)
    item_id = fields.StringField(required=True)
    correct = fields.BooleanField(required=True)
    is_reattempt = fields.BooleanField(default=False)
    attempted_at = fields.DateTimeField(required=True)
