"""Admin registration for core models."""
from django.contrib import admin
from .models import Board, Task


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'owner', 'created_at')
    list_filter = ('owner',)
    search_fields = ('name',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'board', 'status', 'assigned_to', 'created_at')
    list_filter = ('status', 'board')
    search_fields = ('title',)
