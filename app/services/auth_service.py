from app.models.user_models import UserManager
from app.middleware.auth_middleware import verify_cognito_token

class AuthService:
    def __init__(self):
        self.user_manager = UserManager()
    
    def register_user(self, email, password, role='client', company_name: str = ""):
        return self.user_manager.create_user(email, password, role, company_name)
    
    def login_user(self, email, password):
        user = self.user_manager.authenticate_user(email, password)
        if user:
            return {
                "sub": user['user_id'],
                "email": user['email'],
                "role": user['role'],
                "is_active": user.get('is_active', True),
                "company_name": user.get('company_name', "")
            }
        return None

    def verify_token(self, token: str):
        """
        Verify the token from the frontend / client using Cognito.
        """
        return verify_cognito_token(token)
