"""
Global DRF exception handler. Anything DRF already knows how to turn into a clean JSON
response (ValidationError, AuthenticationFailed, Http404, PermissionDenied, ...) passes through
unchanged. Anything else (an unhandled TypeError/KeyError/etc. inside a view) would otherwise
bubble up as a raw Django traceback page or a bare 500 with no body — this wraps those into the
same {"error": {...}} shape so the frontend always has a human-readable message to show instead
of a white screen.
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

HUMAN_MESSAGE = (
    "Something went wrong processing your request. Please try again, "
    "and contact support if the problem continues."
)


def faturathi_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        # Normalize DRF's own error shapes (which vary: {"detail": ...}, {"field": [...]}, a
        # bare list, ...) into a consistent {"error": {code, message, fields}} envelope.
        detail = response.data
        message = detail.get("detail") if isinstance(detail, dict) and "detail" in detail else None
        fields = detail if isinstance(detail, dict) and message is None else None
        if message is None:
            message = str(detail) if not isinstance(detail, (dict, list)) else "The request could not be completed."
        response.data = {
            "error": {
                "code": exc.__class__.__name__,
                "message": str(message),
                "fields": fields,
            }
        }
        return response

    # Unhandled exception: log the real traceback server-side, return a friendly 500 to the client.
    logger.exception("Unhandled exception in %s", context.get("view"))
    return Response(
        {"error": {"code": "SERVER_ERROR", "message": HUMAN_MESSAGE, "fields": None}},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
