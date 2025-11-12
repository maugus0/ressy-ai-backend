import boto3
import os
import uuid
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from app.config import settings
from dotenv import load_dotenv
import os
from typing import Any



dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

# Dynamo Manager
class DynamoDBManager:
    """Main AWS DynamoDB connection and table registry."""
    def __init__(self):
        self.dynamodb: Any = boto3.resource(
            'dynamodb',
            region_name=settings.AWS_REGION,
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )

        # All 9 tables
        self.restaurants_table = self.dynamodb.Table(settings.RESTAURANTS_TABLE)
        self.menus_table = self.dynamodb.Table(settings.MENUS_TABLE)
        self.specials_table = self.dynamodb.Table(settings.SPECIALS_TABLE)
        self.calls_table = self.dynamodb.Table(settings.CALLS_TABLE)
        self.orders_table = self.dynamodb.Table(settings.ORDERS_TABLE)
        self.order_history_table = self.dynamodb.Table(settings.ORDER_HISTORY_TABLE)
        self.transcripts_table = self.dynamodb.Table(settings.TRANSCRIPTS_TABLE)
        self.faqs_table = self.dynamodb.Table(settings.FAQS_TABLE)
        self.users_table = self.dynamodb.Table(settings.USERS_TABLE)

class BaseDynamoManager:
    def __init__(self):
        self.db = DynamoDBManager()

    def _with_retries(self, func, *args, **kwargs):
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


# CallDb
class CallDatabase(BaseDynamoManager):
    def create_call_session(self, user_id, twilio_sid, deepgram_session_id, restaurant_id=None):
        call_id = str(uuid.uuid4())
        item = {
            'call_id': call_id,
            'CALL_METADATA': 'dummy',
            'user_id': user_id,
            'restaurant_id': restaurant_id or "unknown_restaurant",
            'twilio_call_sid': twilio_sid,
            'deepgram_request_id': deepgram_session_id,
            'call_status': 'in_progress',
            'call_direction': 'inbound',
            'started_at': datetime.utcnow().isoformat(),
            'cost': Decimal('0.00'),
            'call_duration': 0,
            'created_at': datetime.utcnow().isoformat()
        }
        print(f"[DDB] put call: user_id={user_id} call_id={call_id}")
        self._with_retries(self.db.calls_table.put_item, Item=item)
        return call_id

    def update_call_cost(self, call_id, duration_seconds):
        cost_per_second = Decimal('0.00009833')
        total_cost = Decimal(str(duration_seconds)) * cost_per_second

        print(f"[DDB] update call: call_id={call_id} duration={duration_seconds} cost={total_cost}")
        self._with_retries(self.db.calls_table.update_item,
            Key={'CALL_METADATA': 'dummy', 'call_id': call_id},
            UpdateExpression='SET call_duration = :dur, cost = :cost, call_status = :status, ended_at = :end',
            ExpressionAttributeValues={
                ':dur': duration_seconds,
                ':cost': total_cost,
                ':status': 'completed',
                ':end': datetime.utcnow().isoformat()
            }
        )
        return total_cost

    def store_transcript(self, call_id, text, is_final=False):
        if not is_final:
            return None  # skip partial results
        existing_items = self.db.transcripts_table.scan(
        FilterExpression=Key('call_id').eq(call_id) & Attr('text').eq(text) & Attr('is_final').eq(True)).get('Items', [])

        if existing_items:
            # Transcript already exists, return its id
            return existing_items[0]['transcript_id']


        transcript_id = str(uuid.uuid4())
        item = {
            'transcript_id': transcript_id,
            'call_id': call_id,
            'text': text,
            'is_final': is_final,
            'timestamp': datetime.utcnow().isoformat()
        }
        print(f"[DDB] put transcript: call_id={call_id} transcript_id={transcript_id} final={is_final}")
        self._with_retries(self.db.transcripts_table.put_item, Item=item)
        return transcript_id

    def get_user_calls(self, user_id, limit=50):
        try:
            response = self._with_retries(
                self.db.calls_table.query,
                IndexName='user_id-index',
                KeyConditionExpression=Key('user_id').eq(user_id),
                Limit=limit,
                ScanIndexForward=False
            )
            return response.get('Items', []) # type: ignore
        except Exception:
            try:
                items = []
                resp = self.db.calls_table.scan(FilterExpression=Attr('user_id').eq(user_id))
                items.extend(resp.get('Items', []))
                items.sort(key=lambda x: x.get('started_at', ''), reverse=True)
                return items[:limit]
            except Exception:
                return []

    def get_call_transcripts(self, call_id):
        response = self.db.transcripts_table.query(KeyConditionExpression=Key('call_id').eq(call_id))
        return response.get('Items', [])
    
    def get_calls_by_restaurant(self, restaurant_id, limit=50):
        """Fetch calls filtered by restaurant_id."""
        try:
            response = self._with_retries(
                self.db.calls_table.query,
                IndexName='restaurant_id-index',
                KeyConditionExpression=Key('restaurant_id').eq(restaurant_id),
                Limit=limit,
                ScanIndexForward=False
            )
            return response.get('Items', []) # type: ignore
        except Exception:
            # fallback to full scan if query fails
            items = []
            resp = self.db.calls_table.scan(FilterExpression=Attr('restaurant_id').eq(restaurant_id))
            items.extend(resp.get('Items', []))
            items.sort(key=lambda x: x.get('started_at', ''), reverse=True)
            return items[:limit]
        
    def get_all_calls(self, limit=50):
        try:
            response = self._with_retries(
                self.db.calls_table.scan  # Use scan because no GSI for all calls
            )
            items = response.get('Items', []) #type: ignore
            items.sort(key=lambda x: x.get('started_at', ''), reverse=True)
            return items[:limit]
        except Exception:
            return []


# User
class UserDatabase(BaseDynamoManager):
    def create_user(self, restaurant_id, email, role='staff', permissions=None):
        user_id = str(uuid.uuid4())
        item = {
            'user_id': user_id,
            'restaurant_id': restaurant_id,
            'email': email,
            'role': role,
            'permissions': permissions or [],
            'status': 'active',
            'created_at': datetime.utcnow().isoformat()
        }
        print(f"[DDB] put user: {email}")
        self.db.users_table.put_item(Item=item)
        return user_id

    def get_users_by_restaurant(self, restaurant_id):
        response = self.db.users_table.query(
            IndexName='restaurant_id-index',
            KeyConditionExpression=Key('restaurant_id').eq(restaurant_id)
        )
        return response.get('Items', [])


# Generic Table Utility
class GenericTableManager(BaseDynamoManager):
    """Reusable for Restaurants, Menus, Specials, Orders, FAQs."""
    def create_item(self, table, item):
        self._with_retries(table.put_item, Item=item)

    def get_item(self, table, key):
        resp = table.get_item(Key=key)
        return resp.get('Item', {})

    def update_item(self, table, key, data):
        data['updated_at'] = datetime.utcnow().isoformat()
        self._with_retries(
            table.update_item,
            Key=key,
            UpdateExpression='SET ' + ', '.join(f'#{k}=:{k}' for k in data.keys()),
            ExpressionAttributeNames={f'#{k}': k for k in data.keys()},
            ExpressionAttributeValues={f':{k}': v for k, v in data.items()}
        )

    def delete_item(self, table, key):
        self._with_retries(table.delete_item, Key=key)

    def scan_table(self, table):
        resp = self._with_retries(table.scan)
        return resp.get('Items', []) # type: ignore
