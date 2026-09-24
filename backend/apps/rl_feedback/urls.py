from django.urls import path

from . import views

urlpatterns = [
    path("status", views.RLStatusView.as_view()),
    path("action", views.RLActionView.as_view()),
]
