"""REST API URL patterns for core app."""
from django.urls import path
from . import views

urlpatterns = [
    path('boards/', views.BoardListCreateView.as_view(), name='board-list-create'),
    path('boards/<int:pk>/', views.BoardDetailView.as_view(), name='board-detail'),
    path('boards/<int:board_id>/tasks/', views.TaskListCreateView.as_view(), name='task-list-create'),
    path('boards/<int:board_id>/tasks/<int:pk>/', views.TaskDetailView.as_view(), name='task-detail'),
    path('me/', views.CurrentUserView.as_view(), name='current-user'),
]
