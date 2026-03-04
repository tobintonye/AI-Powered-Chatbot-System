from django.urls import path
from .views import (
    ChatSessionListCreateView,
    ChatSessionDetailView,
    ArchiveSessionView,
    MessageListView,
    SendMessageView,
)

urlpatterns = [
    # Sessions
    path("sessions/", ChatSessionListCreateView.as_view(), name="session-list-create"),
    path("sessions/<uuid:session_id>/", ChatSessionDetailView.as_view(), name="session-detail"),
    path("sessions/<uuid:session_id>/archive/", ArchiveSessionView.as_view(), name="session-archive"),

    # Messages
    path("sessions/<uuid:session_id>/messages/", SendMessageView.as_view(), name="message-send"),
    path("sessions/<uuid:session_id>/messages/list/", MessageListView.as_view(), name="message-list"),
]
