"""Admin configuration for the chat app."""
from django.contrib import admin
from .models import ChatSession, Message


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "status", "message_count", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "title")
    ordering = ("-updated_at",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "ai_model", "input_tokens", "output_tokens", "created_at")
    list_filter = ("role", "ai_provider", "created_at")
    search_fields = ("session__id", "content")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at")
