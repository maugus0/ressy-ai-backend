import boto3
import os
import uuid
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from app.config.settings import settings

class DynamoDBManager:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', 
            region_name=settings.AWS_REGION,
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
        self.users_table = self.dynamodb.Table(settings.USERS_TABLE)
        self.calls_table = self.dynamodb.Table(settings.CALLS_TABLE)
        self.transcripts_table = self.dynamodb.Table(settings.TRANSCRIPTS_TABLE)

class CallDatabase:
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
    
    def create_call_session(self, user_id, twilio_sid, deepgram_session_id):
        call_id = str(uuid.uuid4())
        item = {
            'call_id': call_id,
            'user_id': user_id,
            'twilio_stream_sid': twilio_sid,
            'deepgram_session_id': deepgram_session_id,
            'start_time': datetime.utcnow().isoformat(),
            'status': 'active',
            'cost': Decimal('0.00'),
            'duration_seconds': 0,
            'created_at': datetime.utcnow().isoformat()
        }
        print(f"[DDB] put calls: user_id={user_id} call_id={call_id}")
        self._with_retries(self.db.calls_table.put_item, Item=item)
        return call_id
    
    def update_call_cost(self, call_id, duration_seconds):
        cost_per_second = Decimal('0.00009833')  
        total_cost = Decimal(str(duration_seconds)) * cost_per_second
        
        print(f"[DDB] update calls: call_id={call_id} duration={duration_seconds} cost={total_cost}")
        self._with_retries(self.db.calls_table.update_item,
            Key={'call_id': call_id},
            UpdateExpression='SET duration_seconds = :dur, cost = :cost, #st = :status, end_time = :end',
            ExpressionAttributeNames={'#st': 'status'},
            ExpressionAttributeValues={
                ':dur': duration_seconds,
                ':cost': total_cost,
                ':status': 'completed',
                ':end': datetime.utcnow().isoformat()
            }
        )
        return total_cost
    
    def store_transcript(self, call_id, text, is_final=False):
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
            response = self._with_retries(self.db.calls_table.query,
                IndexName='user_id-index',
                KeyConditionExpression=Key('user_id').eq(user_id),
                Limit=limit,
                ScanIndexForward=False
            )
            return response.get('Items', [])
        except Exception:
            try:
                from boto3.dynamodb.conditions import Attr
                items = []
                resp = self.db.calls_table.scan(
                    FilterExpression=Attr('user_id').eq(user_id)
                )
                items.extend(resp.get('Items', []))
                items.sort(key=lambda x: x.get('start_time', ''), reverse=True)
                return items[:limit]
            except Exception:
                return []
    
    def get_call_transcripts(self, call_id):
        response = self.db.transcripts_table.query(
            KeyConditionExpression=Key('call_id').eq(call_id)
        )
        return response.get('Items', [])