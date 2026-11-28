import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """Return a stable error envelope and never swallow unhandled exceptions silently."""
    response = exception_handler(exc, context)
    request = context.get("request")
    path = getattr(request, "path", None)
    method = getattr(request, "method", None)

    if response is None:
        logger.exception(
            "unhandled_api_exception",
            extra={"path": path, "method": method, "error_code": "internal_error"},
        )
        return Response(
            {"error": {"code": "internal_error", "message": "An unexpected error occurred."}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    detail = response.data
    code = "invalid_request"
    message = "Request could not be processed."
    if isinstance(detail, dict):
        if "detail" in detail and isinstance(detail["detail"], str):
            message = detail["detail"]
            code = getattr(detail["detail"], "code", code)
        elif "error" in detail:
            return response
        else:
            message = "Validation failed."
            code = "validation_error"
    elif isinstance(detail, list) and detail:
        message = str(detail[0])

    if response.status_code >= 500:
        logger.error(
            "api_error",
            extra={"path": path, "method": method, "status": response.status_code, "error_code": code},
        )
    else:
        logger.info(
            "api_rejected",
            extra={"path": path, "method": method, "status": response.status_code, "error_code": code},
        )

    response.data = {"error": {"code": str(code), "message": message, "details": detail}}
    return response
