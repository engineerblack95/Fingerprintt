"""Consistent JSON error envelopes for the dashboard and the device."""

import logging

from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def _flatten(detail):
    """Turn DRF validation details into a flat list of human-readable strings."""
    if isinstance(detail, dict):
        messages = []
        for field, value in detail.items():
            for message in _flatten(value):
                messages.append(message if field == "non_field_errors" else f"{field}: {message}")
        return messages
    if isinstance(detail, (list, tuple)):
        messages = []
        for item in detail:
            messages.extend(_flatten(item))
        return messages
    return [str(detail)]


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if response is not None:
        detail = response.data
        response.data = {
            "detail": " ".join(_flatten(detail)) or "Request failed.",
            "errors": detail,
            "status_code": response.status_code,
        }
        return response

    if isinstance(exc, Http404):
        return Response(
            {"detail": "Not found.", "errors": [], "status_code": status.HTTP_404_NOT_FOUND},
            status=status.HTTP_404_NOT_FOUND,
        )
    if isinstance(exc, DjangoValidationError):
        messages = _flatten(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        return Response(
            {
                "detail": " ".join(messages),
                "errors": messages,
                "status_code": status.HTTP_400_BAD_REQUEST,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if isinstance(exc, PermissionDenied):
        return Response(
            {"detail": "Permission denied.", "errors": [], "status_code": status.HTTP_403_FORBIDDEN},
            status=status.HTTP_403_FORBIDDEN,
        )
    if isinstance(exc, (APIException, ValidationError)):
        return response

    logger.exception("Unhandled API error: %s", exc)
    return Response(
        {
            "detail": "Internal server error.",
            "errors": [],
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
