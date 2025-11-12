from app.repositories.base import BaseRepository
from typing import Dict, List, Any


class SpamBlocklistRepository(BaseRepository):
    """Repository for spam blocklist data access."""
    
    def _init_tables(self):
        # TODO: Add spam blocklist table when implemented
        pass
    
    def is_blocked(self, phone_number: str) -> bool:
        """Check if a phone number is blocked."""
        # TODO: Implement when spam blocklist table is added
        return False
    
    def add_to_blocklist(self, phone_number: str, reason: str = None) -> None:
        """Add a phone number to the blocklist."""
        # TODO: Implement when spam blocklist table is added
        pass

