"""Custom exception handler for structured error responses."""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


class ChatbotAPIException(Exception):
    """Base chatbot API exception."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = "An unexpected error occurred."
    default_code = "internal_error"

    def __init__(self, message=None, code=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        super().__init__(self.message)


class AIServiceException(ChatbotAPIException):
    """Raised when the AI backend fails."""
    status_code = status.HTTP_502_BAD_GATEWAY
    default_message = "The AI service is temporarily unavailable."
    default_code = "ai_service_error"


class AITimeoutException(ChatbotAPIException):
    """Raised when the AI request times out."""
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    default_message = "The AI service timed out. Please try again."
    default_code = "ai_timeout"


class SessionNotFoundException(ChatbotAPIException):
    """Raised when a chat session is not found."""
    status_code = status.HTTP_404_NOT_FOUND
    default_message = "Chat session not found."
    default_code = "session_not_found"


class SessionExpiredException(ChatbotAPIException):
    """Raised when a chat session has expired."""
    status_code = status.HTTP_410_GONE
    default_message = "This chat session has expired."
    default_code = "session_expired"


def custom_exception_handler(exc, context):
    """
    Custom DRF exception handler that returns consistent JSON error shapes.

    Response format:
    {
        "success": false,
        "error": {
            "code": "error_code",
            "message": "Human-readable message",
            "details": { ... }   // optional extra info
        }
    }
    """
    # First let DRF handle its own exceptions
    response = exception_handler(exc, context)

    if isinstance(exc, ChatbotAPIException):
        logger.error(
            "ChatbotAPIException: %s | code=%s | view=%s",
            exc.message,
            exc.code,
            context.get("view"),
        )
        return Response(
            {
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
            },
            status=exc.status_code,
        )

    if response is not None:
        error_data = {
            "success": False,
            "error": {
                "code": _get_error_code(response.status_code),
                "message": _flatten_errors(response.data),
                "details": response.data,
            },
        }
        response.data = error_data
        return response

    # Unhandled exception → 500
    logger.exception("Unhandled exception in view %s", context.get("view"))
    return Response(
        {
            "success": False,
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred. Please try again later.",
            },
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _get_error_code(status_code: int) -> str:
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "unprocessable_entity",
        429: "rate_limit_exceeded",
        500: "internal_error",
        502: "bad_gateway",
        503: "service_unavailable",
        504: "gateway_timeout",
    }
    return mapping.get(status_code, "error")


def _flatten_errors(data) -> str:
    if isinstance(data, dict):
        messages = []
        for key, val in data.items():
            if key in ("detail",):
                return str(val)
            if isinstance(val, list):
                messages.append(f"{key}: {', '.join(str(v) for v in val)}")
            else:
                messages.append(f"{key}: {val}")
        return "; ".join(messages)
    if isinstance(data, list):
        return ", ".join(str(item) for item in data)
    return str(data)
