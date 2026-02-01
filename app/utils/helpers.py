import re
import uuid
from datetime import datetime, timezone

from app.utils.timezone import isoformat_z


def generate_id():
    return str(uuid.uuid4())


def get_current_time():
    return isoformat_z(datetime.now(timezone.utc))


def normalize_phone_from_words(phone: str) -> str:
    """
    Convert a phone number from word format to digit format.

    Handles cases where the AI model provides phone numbers as words like:
    "plus nine one eight eight five one three one nine four six nine"
    and converts them to: "+918851319469"

    Args:
        phone: Phone number string that may contain words or digits

    Returns:
        Normalized phone number string with digits
    """
    if not phone:
        return phone

    phone = phone.strip().lower()

    # If it's already in digit format (contains digits and common phone chars), return as-is
    if re.search(r"[\d\+\-\(\)\s]", phone) and not re.search(
        r"\b(plus|one|two|three|four|five|six|seven|eight|nine|zero|oh)\b", phone
    ):
        # Already in digit format, just clean it up
        return re.sub(r"[^\d\+]", "", phone)

    # Word to digit mapping
    word_to_digit = {
        "zero": "0",
        "oh": "0",
        "o": "0",
        "one": "1",
        "won": "1",
        "two": "2",
        "to": "2",
        "too": "2",
        "three": "3",
        "tree": "3",
        "four": "4",
        "for": "4",
        "fore": "4",
        "five": "5",
        "fife": "5",
        "six": "6",
        "sicks": "6",
        "seven": "7",
        "eight": "8",
        "ate": "8",
        "nine": "9",
        "nein": "9",
    }

    # Handle "plus" prefix
    has_plus = False
    if phone.startswith("plus") or phone.startswith("+"):
        has_plus = True
        phone = phone.replace("plus", "", 1).strip()
        phone = phone.lstrip("+").strip()

    # Split into words and convert
    words = phone.split()
    digits = []

    for word in words:
        # Remove punctuation
        word = re.sub(r"[^\w]", "", word)
        if not word:
            continue

        # Check if it's already a digit
        if word.isdigit():
            digits.append(word)
        # Check if it's a word representation
        elif word in word_to_digit:
            digits.append(word_to_digit[word])
        # Try to extract digits from the word
        elif re.search(r"\d", word):
            digits.append(re.sub(r"\D", "", word))

    # Join digits
    result = "".join(digits)

    # Add plus prefix if it was explicitly mentioned in the original input
    if has_plus and result:
        result = "+" + result

    return result
