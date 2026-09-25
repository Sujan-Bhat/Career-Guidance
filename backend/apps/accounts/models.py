"""MongoEngine documents for the accounts app (paper FR01: profile management).

Multi-dimensional student profiles live in MongoDB to accommodate the flexible,
evolving schema described in paper Sec. V.
"""
from mongoengine import Document, EmbeddedDocument, fields


class SkillAssessment(EmbeddedDocument):
    skill = fields.StringField(required=True)
    score = fields.FloatField(min_value=0, max_value=100)
    assessed_at = fields.DateTimeField()


class AcademicRecord(EmbeddedDocument):
    subject = fields.StringField(required=True)
    grade = fields.FloatField(min_value=0, max_value=100)
    semester = fields.StringField()
    graded_at = fields.DateTimeField()


class CareerPreference(EmbeddedDocument):
    category = fields.StringField()
    weight = fields.FloatField(min_value=0, max_value=1)


class StudentProfile(Document):
    email = fields.StringField(required=True, unique=True)
    full_name = fields.StringField(required=True)
    password_hash = fields.StringField(required=True)
    institution = fields.StringField()
    programme = fields.StringField()
    year_of_study = fields.IntField()
    academic_records = fields.ListField(fields.EmbeddedDocumentField(AcademicRecord))
    skill_assessments = fields.ListField(fields.EmbeddedDocumentField(SkillAssessment))
    career_preferences = fields.ListField(fields.EmbeddedDocumentField(CareerPreference))
    created_at = fields.DateTimeField()

    meta = {"collection": "profiles", "allow_inheritance": False}
