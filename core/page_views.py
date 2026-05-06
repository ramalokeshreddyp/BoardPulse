"""Page views (HTML rendering) for the task board UI."""
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from .models import Board, Task


class BoardListPageView(LoginRequiredMixin, ListView):
    model = Board
    template_name = 'core/board_list.html'
    context_object_name = 'boards'

    def get_queryset(self):
        return Board.objects.select_related('owner').prefetch_related('tasks').all()


class BoardPageView(LoginRequiredMixin, DetailView):
    model = Board
    template_name = 'core/board.html'
    context_object_name = 'board'
    pk_url_kwarg = 'board_id'

    def get_queryset(self):
        return Board.objects.prefetch_related('tasks__assigned_to').all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        board = self.get_object()
        ctx['todo_tasks'] = board.tasks.filter(status='todo')
        ctx['in_progress_tasks'] = board.tasks.filter(status='in_progress')
        ctx['done_tasks'] = board.tasks.filter(status='done')
        ctx['all_tasks'] = board.tasks.all()
        return ctx
