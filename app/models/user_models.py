import bcrypt
import uuid
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from app.repositories.base import BaseRepository
from app.config import settings

class UserManager:
    def __init__(self):
        # Create a temporary base repository to access DynamoDB
        self.base_repo = BaseRepository()
        self.users_table = self.base_repo.dynamodb.Table(settings.USERS_TABLE)
    
    def create_user(self, email, password, role='client', company_name: str = ""):
        user_id = str(uuid.uuid4())
        
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
        
        item = {
            'user_id': user_id,
            'email': email,
            'password_hash': hashed_password.decode('utf-8'),
            'role': role,
            'company_name': company_name,
            'created_at': datetime.utcnow().isoformat(),
            'is_active': True,
            'total_cost': Decimal('0.00')
        }
        
        try:
            self.users_table.put_item(
                Item=item,
                ConditionExpression='attribute_not_exists(email)'
            )
            return user_id
        except Exception as e:
            raise Exception("User already exists") from e
    
    def authenticate_user(self, email, password):

        try:
            response = self.users_table.query(
                IndexName='email-index',
                KeyConditionExpression=Key('email').eq(email)
            )
            items = response.get('Items') or []
        except Exception:

            try:
                response = self.users_table.scan(
                    FilterExpression=Attr('email').eq(email)
                )
                items = response.get('Items') or []
            except Exception:
                items = []

        print(f"[Auth] Region={settings.AWS_REGION} email={email} items_found={len(items)}")

        if not items:
            return None

        user = items[0]
        try:
            ok = bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8'))
            print(f"[Auth] bcrypt_ok={ok}")
        except Exception as e:
            print(f"[Auth] bcrypt_error={e}")
            ok = False
        if ok:
            return user
        return None
    
    def update_user_cost(self, user_id, cost):
        self.users_table.update_item(
            Key={'user_id': user_id},
            UpdateExpression='ADD total_cost :cost',
            ExpressionAttributeValues={':cost': Decimal(str(cost))}
        )
