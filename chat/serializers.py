"""Chat serializers."""
from rest_framework import serializers
from .models import ChatSession, Message


class MessageSerializer(serializers.ModelSerializer):
    """Serializes a single message."""

    class Meta:
        model = Message
        fields = (
            "id", "role", "content",
            "ai_model", "ai_provider",
            "input_tokens", "output_tokens", "duration_ms",
            "created_at",
        )
        read_only_fields = fields


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(
        min_length=1, max_length=10_000,
        help_text="The user's message text (1–10 000 characters).",
    )


class ChatSessionSerializer(serializers.ModelSerializer):
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = (
            "id", "title", "status",
            "message_count", "created_at", "updated_at",
        )
        read_only_fields = ("id", "message_count", "created_at", "updated_at")

    def get_message_count(self, obj):
        return obj.message_count


class CreateSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ("title",)
        extra_kwargs = {"title": {"required": False, "default": ""}}


class ChatSessionDetailSerializer(ChatSessionSerializer):
    # session with its message history.
    messages = MessageSerializer(many=True, read_only=True)

    class Meta(ChatSessionSerializer.Meta):
        fields = ChatSessionSerializer.Meta.fields + ("messages",)
