"""
Chat Views
==========
RESTful API endpoints for managing chat sessions and sending messages.

Endpoints
---------
GET    /api/chat/sessions/                 — list user's sessions
POST   /api/chat/sessions/                 — create session
GET    /api/chat/sessions/{id}/            — retrieve session + history
PATCH  /api/chat/sessions/{id}/            — update session title
DELETE /api/chat/sessions/{id}/            — delete session
POST   /api/chat/sessions/{id}/archive/   — archive session
POST   /api/chat/sessions/{id}/messages/  — send message & get AI reply
GET    /api/chat/sessions/{id}/messages/  — list messages in session
"""
import logging

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions.handlers import AIServiceException, AITimeoutException

from .models import ChatSession, Message
from .serializers import (
    ChatSessionDetailSerializer,
    ChatSessionSerializer,
    CreateSessionSerializer,
    MessageSerializer,
    SendMessageSerializer,
)
from .services import ChatService

logger = logging.getLogger("apps.chat")


# Session Views 

class ChatSessionListCreateView(generics.ListCreateAPIView):
    """List all sessions or create a new one."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CreateSessionSerializer
        return ChatSessionSerializer

    def get_queryset(self):
        return ChatService.list_sessions(self.request.user)

    @swagger_auto_schema(
        operation_summary="List chat sessions",
        operation_description="Returns all chat sessions for the authenticated user, newest first.",
        responses={200: ChatSessionSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        sessions = self.get_queryset()
        serializer = ChatSessionSerializer(sessions, many=True)
        return Response({"success": True, "data": serializer.data, "count": sessions.count()})

    @swagger_auto_schema(
        operation_summary="Create a new chat session",
        request_body=CreateSessionSerializer,
        responses={201: ChatSessionSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = CreateSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = ChatService.create_session(
            user=request.user,
            title=serializer.validated_data.get("title", ""),
        )
        return Response(
            {"success": True, "data": ChatSessionSerializer(session).data},
            status=status.HTTP_201_CREATED,
        )


class ChatSessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update title, or delete a specific session."""

    permission_classes = [IsAuthenticated]
    serializer_class = ChatSessionDetailSerializer

    def get_object(self):
        return ChatService.get_session(self.kwargs["session_id"], self.request.user)

    @swagger_auto_schema(
        operation_summary="Get session details with message history",
        responses={200: ChatSessionDetailSerializer},
    )
    def get(self, request, *args, **kwargs):
        session = self.get_object()
        serializer = ChatSessionDetailSerializer(session)
        return Response({"success": True, "data": serializer.data})

    @swagger_auto_schema(
        operation_summary="Update session title",
        request_body=CreateSessionSerializer,
        responses={200: ChatSessionSerializer},
    )
    def patch(self, request, *args, **kwargs):
        session = self.get_object()
        serializer = CreateSessionSerializer(session, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        session.refresh_from_db()
        return Response({"success": True, "data": ChatSessionSerializer(session).data})

    @swagger_auto_schema(
        operation_summary="Delete session and all its messages",
        responses={204: "No content"},
    )
    def delete(self, request, *args, **kwargs):
        ChatService.delete_session(self.kwargs["session_id"], request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # Disable PUT
    def put(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class ArchiveSessionView(APIView):
    """Archive a session (soft-delete)."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Archive a chat session",
        responses={200: ChatSessionSerializer},
    )
    def post(self, request, session_id):
        session = ChatService.archive_session(session_id, request.user)
        return Response({"success": True, "data": ChatSessionSerializer(session).data})


# Message Views

class MessageListView(generics.ListAPIView):
    """List all messages in a session (paginated)."""

    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer

    def get_queryset(self):
        session = ChatService.get_session(self.kwargs["session_id"], self.request.user)
        return Message.objects.filter(session=session).order_by("created_at")

    @swagger_auto_schema(
        operation_summary="List messages in a session",
        responses={200: MessageSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(MessageSerializer(page, many=True).data)
        return Response({"success": True, "data": MessageSerializer(queryset, many=True).data})


class SendMessageView(APIView):
    """
    Send a user message and receive an AI response.
    This is the primary chat endpoint.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="30/m", method="POST", block=True))
    @swagger_auto_schema(
        operation_summary="Send a message and get an AI response",
        operation_description=(
            "Sends the user's message, appends it to the session history, "
            "calls the configured AI model, persists the response, and returns both messages.\n\n"
            "Rate limited to **30 requests / minute** per user."
        ),
        request_body=SendMessageSerializer,
        responses={
            200: openapi.Response(
                "Success",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        "data": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "user_message": openapi.Schema(type=openapi.TYPE_OBJECT),
                                "ai_message": openapi.Schema(type=openapi.TYPE_OBJECT),
                                "session_id": openapi.Schema(type=openapi.TYPE_STRING),
                            },
                        ),
                    },
                ),
            ),
            400: "Validation error",
            429: "Rate limit exceeded",
            502: "AI service error",
            504: "AI service timeout",
        },
    )
    def post(self, request, session_id):
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = ChatService.get_session(session_id, request.user)

        if session.status != ChatSession.Status.ACTIVE:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "session_not_active",
                        "message": f"This session is {session.status}. Create a new session to continue chatting.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = ChatService.send_message(
                session=session,
                user_content=serializer.validated_data["content"],
            )
        except AITimeoutException as exc:
            return Response(
                {"success": False, "error": {"code": exc.code, "message": exc.message}},
                status=exc.status_code,
            )
        except AIServiceException as exc:
            return Response(
                {"success": False, "error": {"code": exc.code, "message": exc.message}},
                status=exc.status_code,
            )

        return Response(
            {
                "success": True,
                "data": {
                    "session_id": str(session.id),
                    "user_message": MessageSerializer(result["user_message"]).data,
                    "ai_message": MessageSerializer(result["ai_message"]).data,
                },
            }
        )
