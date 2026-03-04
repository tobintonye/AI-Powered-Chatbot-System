"""Request/response logging middleware."""
import logging
import time
import uuid

logger = logging.getLogger("core")


class RequestLoggingMiddleware:
    """
    Logs every incoming HTTP request and its response.
    Attaches a unique request_id to each request for traceability.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = str(uuid.uuid4())
        request.request_id = request_id
        start_time = time.monotonic()

        logger.info(
            "Incoming request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "user": getattr(request.user, "id", None),
                "ip": self._get_client_ip(request),
            },
        )

        response = self.get_response(request)

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.info(
            "Outgoing response",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        response["X-Request-ID"] = request_id
        return response

    @staticmethod
    def _get_client_ip(request) -> str:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")
