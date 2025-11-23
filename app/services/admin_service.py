from app.repositories.mysql_user_repo import MySQLUserRepository


class AdminService:
    def __init__(self):
        self.user_repo = MySQLUserRepository()

    def get_all_users(self):
        """Get all users - admin only operation."""
        return self.user_repo.list_users()
