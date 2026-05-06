"""
Management command: seed_db

Creates initial data required for testing:
  - 2 users  (user1@example.com, user2@example.com / password123)
  - 1 board  "Project Alpha"
  - 3 tasks  (todo, in_progress, done)

Safe to run multiple times — uses get_or_create throughout.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Board, Task


class Command(BaseCommand):
    help = 'Seed the database with initial test data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...')

        # ── Users ──────────────────────────────────────────────────────────────
        user1, created = User.objects.get_or_create(
            username='user1',
            defaults={'email': 'user1@example.com', 'first_name': 'Alice', 'last_name': 'Smith'},
        )
        if created or not user1.check_password('password123'):
            user1.set_password('password123')
            user1.save()
            self.stdout.write(self.style.SUCCESS(f'  {"Created" if created else "Updated"} user: {user1.email}'))
        else:
            self.stdout.write(f'  User already exists: {user1.email}')

        user2, created = User.objects.get_or_create(
            username='user2',
            defaults={'email': 'user2@example.com', 'first_name': 'Bob', 'last_name': 'Jones'},
        )
        if created or not user2.check_password('password123'):
            user2.set_password('password123')
            user2.save()
            self.stdout.write(self.style.SUCCESS(f'  {"Created" if created else "Updated"} user: {user2.email}'))
        else:
            self.stdout.write(f'  User already exists: {user2.email}')

        # Ensure email is set even if user already existed
        for u, email in [(user1, 'user1@example.com'), (user2, 'user2@example.com')]:
            if u.email != email:
                u.email = email
                u.save(update_fields=['email'])

        # ── Board ──────────────────────────────────────────────────────────────
        board, created = Board.objects.get_or_create(
            name='Project Alpha',
            defaults={'owner': user1},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  Created board: {board.name} (id={board.id})'))
        else:
            self.stdout.write(f'  Board already exists: {board.name} (id={board.id})')

        # ── Tasks ──────────────────────────────────────────────────────────────
        tasks_data = [
            {
                'title': 'Design database schema',
                'description': 'Define all models and relationships for the project.',
                'status': 'todo',
                'assigned_to': user2,
            },
            {
                'title': 'Implement WebSocket consumer',
                'description': 'Build the real-time communication layer using Django Channels.',
                'status': 'in_progress',
                'assigned_to': user1,
            },
            {
                'title': 'Set up Docker Compose',
                'description': 'Containerize the application with web, db, and redis services.',
                'status': 'done',
                'assigned_to': user1,
            },
            {
                'title': 'Write benchmark script',
                'description': 'Load test the WebSocket server for performance analysis.',
                'status': 'todo',
                'assigned_to': None,
            },
            {
                'title': 'Frontend drag-and-drop',
                'description': 'Implement Kanban card dragging with live sync.',
                'status': 'in_progress',
                'assigned_to': user2,
            },
        ]

        for td in tasks_data:
            task, created = Task.objects.get_or_create(
                board=board,
                title=td['title'],
                defaults={
                    'description': td['description'],
                    'status': td['status'],
                    'assigned_to': td['assigned_to'],
                },
            )
            verb = 'Created' if created else 'Already exists'
            self.stdout.write(
                self.style.SUCCESS(f'  {verb} task [{task.status}]: {task.title}') if created
                else f'  {verb} task [{task.status}]: {task.title}'
            )

        self.stdout.write(self.style.SUCCESS('\nDatabase seeded successfully!'))
        self.stdout.write(
            f'\nTest credentials:\n'
            f'  user1@example.com / password123\n'
            f'  user2@example.com / password123\n'
            f'\nBoard ID: {board.id}'
        )
