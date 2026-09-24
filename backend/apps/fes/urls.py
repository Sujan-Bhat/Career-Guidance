from django.urls import path

from . import views

urlpatterns = [
    path("current", views.CurrentFESView.as_view()),
    path("history", views.FESHistoryView.as_view()),
    path("submetrics", views.FESSubmetricsView.as_view()),
]
