"""
BoardConsumer — AsyncWebsocketConsumer for real-time task board collaboration.

Handles:
  - Authentication enforcement (close code 4001 for unauthenticated clients)
  - Task move actions with database persistence
  - Presence tracking via Redis cache (join/leave broadcasts)
  - Group broadcasting via Redis channel layer
"""
import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

PRESENCE_KEY_PREFIX = 'board_presence_'
PRESENCE_TTL = 3600  # 1 hour safety expiry


def _presence_key(board_id: str) -> str:
    return f'{PRESENCE_KEY_PREFIX}{board_id}'


# ──────────────────────────────────────────────────────────────────────────────
# Sync DB helpers (wrapped with database_sync_to_async at call sites)
# ──────────────────────────────────────────────────────────────────────────────

def _update_task_status(task_id: int, new_status: str, board_id: int) -> dict:
    """Update task status in DB and return the updated task data."""
    from .models import Task  # local import to avoid AppRegistry issues
    task = Task.objects.select_related('board', 'assigned_to').get(id=task_id, board_id=board_id)
    task.status = new_status
    task.save(update_fields=['status', 'updated_at'])
    return {
        'id': task.id,
        'title': task.title,
        'status': task.status,
        'board_id': task.board_id,
    }


def _get_board(board_id: int):
    """Fetch a board by ID."""
    from .models import Board
    return Board.objects.get(id=board_id)


# ──────────────────────────────────────────────────────────────────────────────
# Presence helpers (sync — called via database_sync_to_async)
# ──────────────────────────────────────────────────────────────────────────────

def _presence_add(board_id: str, email: str) -> list[str]:
    """Add user to presence set, return updated list."""
    key = _presence_key(board_id)
    users: set = cache.get(key, set())
    users.add(email)
    cache.set(key, users, timeout=PRESENCE_TTL)
    return sorted(users)


def _presence_remove(board_id: str, email: str) -> list[str]:
    """Remove user from presence set, return updated list."""
    key = _presence_key(board_id)
    users: set = cache.get(key, set())
    users.discard(email)
    if users:
        cache.set(key, users, timeout=PRESENCE_TTL)
    else:
        cache.delete(key)
    return sorted(users)


def _presence_get(board_id: str) -> list[str]:
    """Return current presence list."""
    key = _presence_key(board_id)
    users: set = cache.get(key, set())
    return sorted(users)


# ──────────────────────────────────────────────────────────────────────────────
# Consumer
# ──────────────────────────────────────────────────────────────────────────────

class BoardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for a single task board.

    URL pattern: /ws/board/<board_id>/
    """

    # ── lifecycle ──────────────────────────────────────────────────────────────

    async def connect(self):
        self.board_id = self.scope['url_route']['kwargs']['board_id']
        self.board_group_name = f'board_{self.board_id}'
        self.user = self.scope['user']
        self._joined_group = False  # Track whether we joined the channel group

        # Reject unauthenticated connections with code 4001.
        # Must accept() first so the HTTP upgrade completes, then close() sends
        # the proper WebSocket close frame with the custom code.
        if not self.user.is_authenticated:
            logger.warning('Unauthenticated WS connection attempt for board %s', self.board_id)
            await self.accept()
            await self.close(code=4001)
            return

        # Validate board exists
        try:
            await database_sync_to_async(_get_board)(int(self.board_id))
        except Exception:
            logger.warning('WS connect: board %s not found', self.board_id)
            await self.accept()
            await self.close(code=4004)
            return

        # Join the board's channel group
        await self.channel_layer.group_add(self.board_group_name, self.channel_name)
        self._joined_group = True
        await self.accept()

        # Add user to presence and broadcast join event
        online_users = await database_sync_to_async(_presence_add)(
            self.board_id, self.user.email
        )
        await self.channel_layer.group_send(
            self.board_group_name,
            {
                'type': 'presence.update',
                'payload': {
                    'action': 'join',
                    'user': self.user.email,
                    'online_users': online_users,
                },
            }
        )
        logger.info('User %s connected to board %s', self.user.email, self.board_id)

    async def disconnect(self, close_code):
        # Only clean up if we actually joined the group (authenticated + board found)
        if not getattr(self, '_joined_group', False):
            return

        # Remove user from presence and broadcast leave event
        if self.user.is_authenticated:
            online_users = await database_sync_to_async(_presence_remove)(
                self.board_id, self.user.email
            )
            await self.channel_layer.group_send(
                self.board_group_name,
                {
                    'type': 'presence.update',
                    'payload': {
                        'action': 'leave',
                        'user': self.user.email,
                        'online_users': online_users,
                    },
                }
            )
            logger.info('User %s disconnected from board %s (code=%s)',
                        self.user.email, self.board_id, close_code)

        await self.channel_layer.group_discard(self.board_group_name, self.channel_name)

    # ── receive ────────────────────────────────────────────────────────────────

    async def receive(self, text_data):
        """Handle incoming WebSocket messages from the client."""
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error('Invalid JSON')
            return

        action = data.get('action')
        logger.debug('Board %s received action=%s from %s', self.board_id, action, self.user.email)

        if action == 'move_task':
            await self._handle_move_task(data)
        elif action == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong', 'timestamp': data.get('timestamp')}))
        else:
            await self._send_error(f'Unknown action: {action}')

    async def _handle_move_task(self, data: dict):
        task_id = data.get('task_id')
        new_status = data.get('new_status')

        VALID_STATUSES = {'todo', 'in_progress', 'done'}
        if not task_id or new_status not in VALID_STATUSES:
            await self._send_error('Invalid task_id or new_status')
            return

        try:
            task_data = await database_sync_to_async(_update_task_status)(
                int(task_id), new_status, int(self.board_id)
            )
        except Exception as exc:
            logger.error('Failed to update task %s: %s', task_id, exc)
            await self._send_error(f'Task update failed: {exc}')
            return

        # Broadcast to all clients in the board group (including sender)
        await self.channel_layer.group_send(
            self.board_group_name,
            {
                'type': 'task.moved',
                'task_id': task_data['id'],
                'new_status': task_data['status'],
                'moved_by': self.user.email,
            }
        )

    # ── group event handlers ───────────────────────────────────────────────────

    async def task_moved(self, event):
        """Relay task.moved group event to the connected WebSocket client."""
        await self.send(text_data=json.dumps({
            'type': 'task.moved',
            'task_id': event['task_id'],
            'new_status': event['new_status'],
            'moved_by': event['moved_by'],
        }))

    async def presence_update(self, event):
        """Relay presence.update group event to the connected WebSocket client."""
        await self.send(text_data=json.dumps({
            'type': 'presence',
            'payload': event['payload'],
        }))

    # ── utility ────────────────────────────────────────────────────────────────

    async def _send_error(self, message: str):
        await self.send(text_data=json.dumps({'type': 'error', 'message': message}))
