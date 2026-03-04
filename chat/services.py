"""
Chat Service
Encapsulates all business logic for managing sessions and generating AI responses.
Views stay thin — they delegate everything here.
"""
import logging

from django.conf import settings
from django.contrib.auth.models import User

from ai_service.providers import AIMessage, get_provider
from core.exceptions.handlers import AIServiceException, SessionNotFoundException

from .models import ChatSession, Message

logger = logging.getLogger("apps.chat")

# Max history messages sent to the AI as context
CONTEXT_WINDOW = 20


class ChatService:
    """Stateless service object for chat operations."""

    # Sessions
    @staticmethod
    def create_session(user: User, title: str = "") -> ChatSession:
        session = ChatSession.objects.create(user=user, title=title or "New Conversation")
        logger.info("Session created: id=%s user=%s", session.id, user.id)
        return session

    @staticmethod
    def get_session(session_id: str, user: User) -> ChatSession:
        try:
            return ChatSession.objects.get(id=session_id, user=user)
        except ChatSession.DoesNotExist:
            raise SessionNotFoundException()

    @staticmethod
    def list_sessions(user: User):
        return ChatSession.objects.filter(user=user)

    @staticmethod
    def archive_session(session_id: str, user: User) -> ChatSession:
        session = ChatService.get_session(session_id, user)
        session.status = ChatSession.Status.ARCHIVED
        session.save(update_fields=["status", "updated_at"])
        logger.info("Session archived: id=%s user=%s", session.id, user.id)
        return session

    @staticmethod
    def delete_session(session_id: str, user: User) -> None:
        session = ChatService.get_session(session_id, user)
        session.delete()
        logger.info("Session deleted: id=%s user=%s", session_id, user.id)

    # Messaging 

    @staticmethod
    def send_message(session: ChatSession, user_content: str) -> dict:
        """
        Persist the user message, call the AI, persist the response.
        Returns a dict with both messages.
        """

        user_msg = Message.objects.create(
            session=session,
            role=Message.Role.USER,
            content=user_content.strip(),
        )
        logger.debug("User message saved: id=%s session=%s", user_msg.id, session.id)

        history_qs = session.messages.order_by("-created_at")[: CONTEXT_WINDOW]
        history = [
            AIMessage(role=m.role, content=m.content)
            for m in reversed(list(history_qs))
        ]

        if session.title in ("", "New Conversation") and session.message_count <= 2:
            truncated = user_content[:60].strip()
            session.title = truncated if len(user_content) <= 60 else truncated + "…"
            session.save(update_fields=["title", "updated_at"])

        system_prompt = settings.AI_SYSTEM_PROMPT
        max_tokens = settings.AI_MAX_TOKENS

        try:
            provider = get_provider()
            ai_response = provider.complete(
                messages=history,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
            )
        except (AIServiceException,) as exc:
            fallback = Message.objects.create(
                session=session,
                role=Message.Role.ASSISTANT,
                content=exc.message,
            )
            logger.warning(
                "AI service error; fallback message saved: session=%s error=%s",
                session.id, exc.message,
            )
            raise  # Re-raise so the view can return the correct HTTP status

        ai_msg = Message.objects.create(
            session=session,
            role=Message.Role.ASSISTANT,
            content=ai_response.content,
            ai_model=ai_response.model,
            ai_provider=ai_response.provider,
            input_tokens=ai_response.input_tokens,
            output_tokens=ai_response.output_tokens,
            duration_ms=ai_response.duration_ms,
        )

        session.save(update_fields=["updated_at"])

        logger.info(
            "AI message saved: session=%s tokens_in=%d tokens_out=%d ms=%s",
            session.id, ai_response.input_tokens, ai_response.output_tokens, ai_response.duration_ms,
        )

        return {"user_message": user_msg, "ai_message": ai_msg}
