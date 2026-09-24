from django.urls import path

from . import views

urlpatterns = [
    path("sessions/start", views.SessionStartView.as_view()),
    path("sessions/<str:session_id>/end", views.SessionEndView.as_view()),
    path("events/batch", views.EventBatchView.as_view()),
]
