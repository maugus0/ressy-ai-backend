from app.repositories.base import BaseRepository
from app.repositories.mock_data import MOCK_DATA


class SpamBlocklistRepository(BaseRepository):
    """Repository for spam blocklist data access."""

    def _init_tables(self):
        # TODO: Add spam blocklist table when implemented
        self.blocklist_table = None

    def is_blocked(self, phone_number: str) -> bool:
        """Check if a phone number is blocked."""
        if self.use_mock:
            return phone_number in MOCK_DATA["blocklist"]
        return False

    def add_to_blocklist(self, phone_number: str, reason: str = None) -> None:
        """Add a phone number to the blocklist."""
        if self.use_mock:
            MOCK_DATA["blocklist"].add(phone_number)
