import uuid
from django.contrib.auth.models import User
from django.db import models


class ChatSession(models.Model):
    """Represents a single conversation thread between a user and the AI."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_sessions")
    title = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["-updated_at"]),
        ]

    def __str__(self):
        return f"Session({self.id}) — {self.user.username}"

    @property
    def message_count(self):
        return self.messages.count()

    def get_history(self, limit: int = 50):
        """Return the last `limit` messages for context building."""
        return self.messages.order_by("created_at").select_related()[:limit]


class Message(models.Model):
    """A single message within a ChatSession."""

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()

    # AI metadata (populated only for assistant messages)
    ai_model = models.CharField(max_length=100, blank=True, default="")
    ai_provider = models.CharField(max_length=50, blank=True, default="")
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    duration_ms = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"]),
        ]

    def __str__(self):
        return f"Message({self.role}) in Session({self.session_id})"
