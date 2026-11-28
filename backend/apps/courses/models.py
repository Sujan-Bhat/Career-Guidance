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

    meta = {"collection": "resources", "allow_inheritance": False}


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

class CodingProblem(Document):
    slug = fields.StringField(required=True, unique=True)
    question_id = fields.StringField()
    title = fields.StringField(required=True)
    difficulty = fields.StringField(choices=("Easy", "Medium", "Hard"), required=True)
    topic_tags = fields.ListField(fields.StringField())
    content = fields.StringField()  # HTML description from LeetCode
    starter_code = fields.DictField()  # {"python3": "...", "javascript": "..."}
    example_testcases = fields.StringField()

    meta = {"collection": "coding_problems", "allow_inheritance": False}


class CodeSubmission(Document):
    student = fields.StringField(required=True)
    problem_slug = fields.StringField(required=True)
    language = fields.StringField(required=True)
    code = fields.StringField(required=True)
    passed = fields.BooleanField(default=False)
    source = fields.StringField(default="careermind")  # careermind | leetcode
    submitted_at = fields.DateTimeField(required=True)

    meta = {
        "collection": "code_submissions",
        "indexes": [("student", "problem_slug")],
        "allow_inheritance": False,
    }