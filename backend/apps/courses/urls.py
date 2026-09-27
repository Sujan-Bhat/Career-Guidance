from django.urls import path

from . import views

urlpatterns = [
    path("", views.CourseListView.as_view()),
    path("quizzes", views.QuizListView.as_view()),
    path("quizzes/<str:quiz_id>", views.QuizDetailView.as_view()),
    path("quizzes/<str:quiz_id>/attempt", views.QuizAttemptView.as_view()),
]
