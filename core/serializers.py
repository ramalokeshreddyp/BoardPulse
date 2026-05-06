"""DRF Serializers for Board and Task models."""
from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Board, Task


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class TaskSerializer(serializers.ModelSerializer):
    assigned_to = UserSerializer(read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='assigned_to',
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'board', 'status',
            'assigned_to', 'assigned_to_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'board', 'created_at', 'updated_at']


class BoardSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    tasks = TaskSerializer(many=True, read_only=True)
    task_count = serializers.SerializerMethodField()

    class Meta:
        model = Board
        fields = ['id', 'name', 'owner', 'tasks', 'task_count', 'created_at']
        read_only_fields = ['id', 'owner', 'created_at']

    def get_task_count(self, obj):
        return obj.tasks.count()


class BoardListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list endpoints (no nested tasks)."""
    owner = UserSerializer(read_only=True)
    task_count = serializers.SerializerMethodField()

    class Meta:
        model = Board
        fields = ['id', 'name', 'owner', 'task_count', 'created_at']
        read_only_fields = ['id', 'owner', 'created_at']

    def get_task_count(self, obj):
        return obj.tasks.count()
