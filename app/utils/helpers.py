import uuid
from datetime import datetime


def generate_id():
    return str(uuid.uuid4())


def get_current_time():
    return datetime.utcnow().isoformat()
