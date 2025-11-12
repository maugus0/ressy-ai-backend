import boto3
import os
from typing import Any
from app.config import settings


class BaseRepository:
    """Base repository with common DynamoDB operations."""
    
    def __init__(self):
        self.dynamodb: Any = boto3.resource(
            'dynamodb',
            region_name=settings.AWS_REGION,
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        self._init_tables()
    
    def _init_tables(self):
        """Initialize table references. Override in subclasses."""
        pass
    
    def _with_retries(self, func, *args, **kwargs):
        """Retry wrapper for DynamoDB operations."""
        attempts = 0
        last_err = None
        while attempts < 3:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                attempts += 1
                last_err = e
                print(f"[DDB] attempt {attempts} failed for {func.__name__}: {e}")
        if last_err:
            raise last_err

