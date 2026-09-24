from django.urls import path

from . import views

urlpatterns = [
    path("chat", views.ChatView.as_view()),
    path("quiz/generate", views.QuizGenerateView.as_view()),
]
