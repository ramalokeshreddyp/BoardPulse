"""WSGI config — kept for compatibility but Daphne uses ASGI."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'taskboard.settings')
application = get_wsgi_application()
