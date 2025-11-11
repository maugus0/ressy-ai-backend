import uuid
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from app.repositories.base import BaseRepository
from app.config import settings
from typing import Dict, List, Any


class CallRepository(BaseRepository):
    """Repository for call data access."""
    
    def _init_tables(self):
        self.calls_table = self.dynamodb.Table(settings.CALLS_TABLE)
        self.transcripts_table = self.dynamodb.Table(settings.TRANSCRIPTS_TABLE)
    
    def create_call_session(self, user_id: str, twilio_sid: str, deepgram_session_id: str, restaurant_id: str = None) -> str:
        """Create a new call session."""
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
        self._with_retries(self.calls_table.put_item, Item=item)
        return call_id
    
    def update_call_cost(self, call_id: str, duration_seconds: int) -> Decimal:
        """Update call cost and duration."""
        cost_per_second = Decimal('0.00009833')
        total_cost = Decimal(str(duration_seconds)) * cost_per_second
        
        print(f"[DDB] update call: call_id={call_id} duration={duration_seconds} cost={total_cost}")
        self._with_retries(
            self.calls_table.update_item,
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
    
    def get_user_calls(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get calls for a user."""
        try:
            response = self._with_retries(
                self.calls_table.query,
                IndexName='user_id-index',
                KeyConditionExpression=Key('user_id').eq(user_id),
                Limit=limit,
                ScanIndexForward=False
            )
            return response.get('Items', [])
        except Exception:
            try:
                items = []
                resp = self.calls_table.scan(FilterExpression=Attr('user_id').eq(user_id))
                items.extend(resp.get('Items', []))
                items.sort(key=lambda x: x.get('started_at', ''), reverse=True)
                return items[:limit]
            except Exception:
                return []
    
    def get_calls_by_restaurant(self, restaurant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get calls for a restaurant."""
        try:
            response = self._with_retries(
                self.calls_table.query,
                IndexName='restaurant_id-index',
                KeyConditionExpression=Key('restaurant_id').eq(restaurant_id),
                Limit=limit,
                ScanIndexForward=False
            )
            return response.get('Items', [])
        except Exception:
            items = []
            resp = self.calls_table.scan(FilterExpression=Attr('restaurant_id').eq(restaurant_id))
            items.extend(resp.get('Items', []))
            items.sort(key=lambda x: x.get('started_at', ''), reverse=True)
            return items[:limit]
    
    def get_all_calls(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all calls."""
        try:
            response = self._with_retries(self.calls_table.scan)
            items = response.get('Items', [])
            items.sort(key=lambda x: x.get('started_at', ''), reverse=True)
            return items[:limit]
        except Exception:
            return []
    
    def store_transcript(self, call_id: str, message_sequence: int, speaker: str, message: str, timestamp: str) -> None:
        """Store a transcript item."""
        transcript_item = {
            "call_id": call_id,
            "message_sequence": message_sequence,
            "speaker": speaker,
            "message": message,
            "timestamp": timestamp
        }
        print(f"[DDB] put transcript: call_id={call_id} seq={message_sequence} speaker={speaker}")
        self._with_retries(self.transcripts_table.put_item, Item=transcript_item)
    
    def get_call_transcripts(self, call_id: str) -> List[Dict[str, Any]]:
        """Get transcripts for a call."""
        response = self._with_retries(
            self.transcripts_table.query,
            KeyConditionExpression=Key('call_id').eq(call_id)
        )
        return response.get('Items', [])
    
    def delete_transcript(self, transcript_id: str) -> None:
        """Delete a transcript."""
        # Note: This may need to be updated based on actual table structure
        # For now, we'll use a scan to find and delete
        try:
            response = self._with_retries(
                self.transcripts_table.scan,
                FilterExpression="transcript_id = :tid",
                ExpressionAttributeValues={":tid": transcript_id}
            )
            items = response.get('Items', [])
            for item in items:
                # Delete based on actual key structure
                # This is a placeholder - adjust based on your table structure
                self._with_retries(
                    self.transcripts_table.delete_item,
                    Key={"transcript_id": transcript_id}
                )
        except Exception as e:
            print(f"Error deleting transcript: {e}")

