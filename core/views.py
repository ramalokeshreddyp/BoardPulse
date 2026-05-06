"""REST API views for boards and tasks."""
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User

from .models import Board, Task
from .serializers import BoardSerializer, BoardListSerializer, TaskSerializer


class BoardListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/boards/  — List all boards
    POST /api/boards/  — Create a new board
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Board.objects.select_related('owner').prefetch_related('tasks').all()

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return BoardListSerializer
        return BoardSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class BoardDetailView(generics.RetrieveAPIView):
    """
    GET /api/boards/{board_id}/ — Retrieve a single board with tasks
    """
    queryset = Board.objects.select_related('owner').prefetch_related('tasks__assigned_to').all()
    serializer_class = BoardSerializer
    permission_classes = [permissions.IsAuthenticated]


class TaskListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/boards/{board_id}/tasks/  — List all tasks for a board
    POST /api/boards/{board_id}/tasks/  — Create a task for a board
    """
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        board_id = self.kwargs['board_id']
        board = get_object_or_404(Board, id=board_id)
        return Task.objects.filter(board=board).select_related('assigned_to')

    def perform_create(self, serializer):
        board_id = self.kwargs['board_id']
        board = get_object_or_404(Board, id=board_id)
        serializer.save(board=board)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class TaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE /api/boards/{board_id}/tasks/{task_id}/
    """
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        board_id = self.kwargs['board_id']
        return Task.objects.filter(board_id=board_id).select_related('assigned_to')


class CurrentUserView(APIView):
    """GET /api/me/ — Returns the currently authenticated user."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
        })
