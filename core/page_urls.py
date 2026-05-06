"""Page/HTML view URL patterns."""
from django.urls import path
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView
from . import page_views

urlpatterns = [
    path('', login_required(page_views.BoardListPageView.as_view()), name='home'),
    path('boards/<int:board_id>/', login_required(page_views.BoardPageView.as_view()), name='board-page'),
]
