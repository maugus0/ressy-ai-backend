from app.models.user_models import UserManager
from app.utils.security import JWTManager

class AuthService:
    def __init__(self):
        self.user_manager = UserManager()
        self.jwt_manager = JWTManager()
    
    def register_user(self, email, password, role='client', company_name: str = ""):
        return self.user_manager.create_user(email, password, role, company_name)
    
    def login_user(self, email, password):
        user = self.user_manager.authenticate_user(email, password)
        if user:
            token = self.jwt_manager.create_access_token(
                data={
                    "sub": user['user_id'],
                    "email": user['email'],
                    "role": user['role'],
                    "is_active": user.get('is_active', True),
                    "company_name": user.get('company_name', "")
                }
            )
            return token
        return None