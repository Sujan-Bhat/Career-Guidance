"""MongoEngine documents for the RL adaptive feedback log (paper FR07)."""
from mongoengine import Document, fields


class RLTransition(Document):
    """One (state, action, reward, done) tuple per student-session.

    State layout (17-dim, paper Sec. V-C):
      [0:5]   last five session FES values
      [5:10]  five key subject grades
      [10:15] top five skill-assessment scores
      [15]    active career-pathway identifier (scalar)
      [16]    recommendation acceptance/rejection ratio over last ten sessions
    """

    student = fields.StringField(required=True)
    state = fields.ListField(fields.FloatField(), required=True)
    action = fields.IntField(min_value=0, max_value=7, required=True)
    reward = fields.FloatField(required=True)
    done = fields.BooleanField(default=False)
    created_at = fields.DateTimeField(required=True)
