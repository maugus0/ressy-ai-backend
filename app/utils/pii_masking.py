"""Utilities for masking PII (Personally Identifiable Information) in logs.

This module provides functions to safely log sensitive data like phone numbers
and email addresses without exposing full values, helping maintain GDPR/CCPA
compliance.
"""


def mask_phone_number(phone: str | None) -> str:
    """Mask a phone number for safe logging, showing only last 4 digits.

    Args:
        phone: The phone number to mask, or None.

    Returns:
        Masked phone number (e.g., "+14155551234" -> "********1234")
        or "None"/"" for empty values.

    Examples:
        >>> mask_phone_number("+14155551234")
        '********1234'
        >>> mask_phone_number("5551234")
        '***1234'
        >>> mask_phone_number(None)
        'None'
        >>> mask_phone_number("")
        ''
    """
    if phone is None:
        return "None"
    if not phone:
        return ""
    phone_str = str(phone).strip()
    if len(phone_str) <= 4:
        return phone_str
    return "*" * (len(phone_str) - 4) + phone_str[-4:]


def mask_email(email: str | None) -> str:
    """Mask an email address for safe logging.

    Shows only the first and last characters of the local part, with the
    domain fully visible for debugging purposes.

    Args:
        email: The email to mask, or None.

    Returns:
        Masked email (e.g., "john.doe@example.com" -> "j*******e@example.com")

    Examples:
        >>> mask_email("john.doe@example.com")
        'j*******e@example.com'
        >>> mask_email("ab@test.com")
        'a*@test.com'
        >>> mask_email(None)
        'None'
    """
    if email is None:
        return "None"
    if not email or "@" not in email:
        return email or ""
    local, domain = email.rsplit("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*" if len(local) > 0 else "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"
