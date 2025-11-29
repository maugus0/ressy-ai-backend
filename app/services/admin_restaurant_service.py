"""
Admin Restaurant Service for managing restaurants.
"""
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository
from typing import Dict, Optional, List
from fastapi import HTTPException
import json
import re
import math

class AdminRestaurantService:
    """Service for admin restaurant management operations."""
    
    def __init__(self):
        self.restaurant_repo = MySQLRestaurantRepository()
    
    def _validate_phone_number(self, phone_number: Optional[str]) -> None:
        """Validate phone number format."""
        if phone_number and len(phone_number) > 20:
            raise HTTPException(status_code=400, detail="Phone number must be 20 characters or less")
        if phone_number and not re.match(r'^[\d\s\-\+\(\)]+$', phone_number):
            raise HTTPException(status_code=400, detail="Invalid phone number format")
    
    def _validate_json_field(self, field_name: str, value: Optional[Dict]) -> None:
        """Validate JSON field structure."""
        if value is not None and not isinstance(value, dict):
            raise HTTPException(status_code=400, detail=f"{field_name} must be a valid JSON object")
    
    def _validate_minutes(self, minutes: Optional[int], field_name: str) -> None:
        """Validate minute values are non-negative integers."""
        if minutes is not None and minutes < 0:
            raise HTTPException(status_code=400, detail=f"{field_name} must be a non-negative integer")
    
    def create_restaurant(self, data: Dict) -> Dict:
        """Create a new restaurant."""
        # Validate required fields
        if not data.get('name'):
            raise HTTPException(status_code=400, detail="name is required")
        if len(data.get('name', '')) > 255:
            raise HTTPException(status_code=400, detail="name must be 255 characters or less")
        
        # Validate optional fields
        self._validate_phone_number(data.get('phone_number'))
        self._validate_phone_number(data.get('twilio_phone_number'))
        self._validate_json_field('twilio_details', data.get('twilio_details'))
        self._validate_json_field('deepgram_details', data.get('deepgram_details'))
        self._validate_json_field('open_table_details', data.get('open_table_details'))
        self._validate_minutes(data.get('forward_minutes'), 'forward_minutes')
        self._validate_minutes(data.get('backward_minutes'), 'backward_minutes')
        
        # Set defaults
        restaurant_data = {
            'name': data['name'],
            'address': data.get('address'),
            'phone_number': data.get('phone_number'),
            'twilio_phone_number': data.get('twilio_phone_number'),
            'twilio_details': data.get('twilio_details'),
            'deepgram_details': data.get('deepgram_details'),
            'open_table_details': data.get('open_table_details'),
            'forward_minutes': data.get('forward_minutes', 0),
            'backward_minutes': data.get('backward_minutes', 0),
            'is_credit_card_required_for_reservation': data.get('is_credit_card_required_for_reservation', False)
        }
        
        try:
            restaurant_id = self.restaurant_repo.create(restaurant_data)
            restaurant = self.restaurant_repo.get_by_id(restaurant_id)
            if not restaurant:
                raise HTTPException(status_code=500, detail="Failed to retrieve created restaurant")
            
            # Parse JSON fields
            if restaurant.get('twilio_details'):
                restaurant['twilio_details'] = json.loads(restaurant['twilio_details']) if isinstance(restaurant['twilio_details'], str) else restaurant['twilio_details']
            if restaurant.get('deepgram_details'):
                restaurant['deepgram_details'] = json.loads(restaurant['deepgram_details']) if isinstance(restaurant['deepgram_details'], str) else restaurant['deepgram_details']
            if restaurant.get('open_table_details'):
                restaurant['open_table_details'] = json.loads(restaurant['open_table_details']) if isinstance(restaurant['open_table_details'], str) else restaurant['open_table_details']
            
            return restaurant
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create restaurant: {str(e)}")
    
    def get_all_restaurants(
        self,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        is_credit_card_required: Optional[bool] = None
    ) -> Dict:
        """Get all restaurants with pagination, search, and filtering."""
        # Validate pagination parameters
        if page < 1:
            page = 1
        if limit < 1:
            limit = 20
        if limit > 100:
            limit = 100
        
        try:
            restaurants, total = self.restaurant_repo.get_all(page, limit, search, is_credit_card_required)
            total_pages = math.ceil(total / limit) if limit > 0 else 0
            
            return {
                'data': restaurants,
                'total': total,
                'page': page,
                'limit': limit,
                'total_pages': total_pages
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve restaurants: {str(e)}")
    
    def get_restaurant_by_id(self, restaurant_id: int) -> Dict:
        """Get restaurant by ID."""
        try:
            restaurant = self.restaurant_repo.get_by_id(restaurant_id)
            if not restaurant:
                raise HTTPException(status_code=404, detail="Restaurant not found")
            
            # Parse JSON fields
            if restaurant.get('twilio_details'):
                restaurant['twilio_details'] = json.loads(restaurant['twilio_details']) if isinstance(restaurant['twilio_details'], str) else restaurant['twilio_details']
            if restaurant.get('deepgram_details'):
                restaurant['deepgram_details'] = json.loads(restaurant['deepgram_details']) if isinstance(restaurant['deepgram_details'], str) else restaurant['deepgram_details']
            if restaurant.get('open_table_details'):
                restaurant['open_table_details'] = json.loads(restaurant['open_table_details']) if isinstance(restaurant['open_table_details'], str) else restaurant['open_table_details']
            
            return restaurant
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve restaurant: {str(e)}")
    
    def update_restaurant(self, restaurant_id: int, data: Dict) -> Dict:
        """Update restaurant by ID."""
        # Check if restaurant exists
        existing = self.restaurant_repo.get_by_id(restaurant_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        
        # Validate fields if provided
        if 'name' in data and len(data.get('name', '')) > 255:
            raise HTTPException(status_code=400, detail="name must be 255 characters or less")
        if 'phone_number' in data:
            self._validate_phone_number(data.get('phone_number'))
        if 'twilio_phone_number' in data:
            self._validate_phone_number(data.get('twilio_phone_number'))
        if 'twilio_details' in data:
            self._validate_json_field('twilio_details', data.get('twilio_details'))
        if 'deepgram_details' in data:
            self._validate_json_field('deepgram_details', data.get('deepgram_details'))
        if 'open_table_details' in data:
            self._validate_json_field('open_table_details', data.get('open_table_details'))
        if 'forward_minutes' in data:
            self._validate_minutes(data.get('forward_minutes'), 'forward_minutes')
        if 'backward_minutes' in data:
            self._validate_minutes(data.get('backward_minutes'), 'backward_minutes')
        
        try:
            success = self.restaurant_repo.update(restaurant_id, data)
            if not success:
                raise HTTPException(status_code=400, detail="No fields to update")
            
            restaurant = self.restaurant_repo.get_by_id(restaurant_id)
            if not restaurant:
                raise HTTPException(status_code=500, detail="Failed to retrieve updated restaurant")
            
            # Parse JSON fields
            if restaurant.get('twilio_details'):
                restaurant['twilio_details'] = json.loads(restaurant['twilio_details']) if isinstance(restaurant['twilio_details'], str) else restaurant['twilio_details']
            if restaurant.get('deepgram_details'):
                restaurant['deepgram_details'] = json.loads(restaurant['deepgram_details']) if isinstance(restaurant['deepgram_details'], str) else restaurant['deepgram_details']
            if restaurant.get('open_table_details'):
                restaurant['open_table_details'] = json.loads(restaurant['open_table_details']) if isinstance(restaurant['open_table_details'], str) else restaurant['open_table_details']
            
            return restaurant
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update restaurant: {str(e)}")
    
    def delete_restaurant(self, restaurant_id: int) -> Dict:
        """Delete restaurant by ID."""
        # Check if restaurant exists
        existing = self.restaurant_repo.get_by_id(restaurant_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        
        try:
            success = self.restaurant_repo.delete(restaurant_id)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to delete restaurant")
            
            return {"message": "Restaurant deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete restaurant: {str(e)}")
    
    def get_restaurant_statistics(self, restaurant_id: int) -> Dict:
        """Get statistics for a restaurant."""
        # Check if restaurant exists
        existing = self.restaurant_repo.get_by_id(restaurant_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        
        try:
            stats = self.restaurant_repo.get_statistics(restaurant_id)
            return stats
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve restaurant statistics: {str(e)}")

