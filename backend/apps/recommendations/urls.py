from django.urls import path

from . import views

urlpatterns = [
    path("", views.RecommendationListView.as_view()),
    path("<str:recommendation_id>/accept", views.AcceptView.as_view()),
    path("<str:recommendation_id>/reject", views.RejectView.as_view()),
    path("<str:recommendation_id>/explain", views.ExplainView.as_view()),
]
