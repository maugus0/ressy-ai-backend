"""
OpenTable API Client for making requests to OpenTable's API.
"""
import requests
from typing import Dict, Optional, Any
import json
from app.config import settings


class OpenTableClient:
    """Client for OpenTable API integration."""
    
    def __init__(self, base_url: Optional[str] = None, bearer_token: Optional[str] = None):
        """
        Initialize OpenTable client.
        
        Args:
            base_url: OpenTable API base URL (defaults to OPENTABLE_BASE_URL from config)
            bearer_token: Bearer token for authentication
        """
        self.base_url = base_url or settings.OPENTABLE_BASE_URL
        self.bearer_token = bearer_token
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        headers = {
            "Content-Type": "application/json"
        }
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers
    
    def get_availability(
        self,
        rid: int,
        start_date_time: str,
        forward_minutes: Optional[int] = None,
        backward_minutes: Optional[int] = None,
        party_size: Optional[int] = None,
        require_attributes: Optional[str] = None,
        include_credit_card_results: Optional[bool] = None,
        include_experiences: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Get table availability for a restaurant.
        
        Args:
            rid: Restaurant ID
            start_date_time: Start date and time in format yyyy-mm-ddThh:ss
            forward_minutes: Forward booking window in minutes
            backward_minutes: Backward booking window in minutes
            party_size: Party size
            require_attributes: Table types (comma-separated)
            include_credit_card_results: Include credit card results
            include_experiences: Include experiences
        
        Returns:
            API response as dictionary
        """
        url = f"{self.base_url}/v2/availability/{rid}"
        params = {
            "start_date_time": start_date_time
        }
        
        if forward_minutes is not None:
            params["forward_minutes"] = forward_minutes
        if backward_minutes is not None:
            params["backward_minutes"] = backward_minutes
        if party_size is not None:
            params["party_size"] = party_size
        if require_attributes:
            params["require_attributes"] = require_attributes
        if include_credit_card_results is not None:
            params["include_credit_card_results"] = str(include_credit_card_results).lower()
        if include_experiences is not None:
            params["include_experiences"] = str(include_experiences).lower()
        
        response = requests.get(url, params=params, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def lock_slot(
        self,
        rid: int,
        party_size: int,
        date_time: str,
        reservation_attribute: str = "default",
        experience: Optional[Dict[str, Any]] = None,
        dining_area_id: Optional[int] = None,
        environment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Lock a booking slot.
        
        Args:
            rid: Restaurant ID
            party_size: Party size
            date_time: Date and time in format yyyy-mm-ddThh:ss
            reservation_attribute: Reservation attribute (default: "default")
            experience: Experience details (optional)
            dining_area_id: Dining area ID (optional)
            environment: Environment (e.g., "Indoor", "Outdoor") (optional)
        
        Returns:
            API response with reservation_token and expires_at
        """
        url = f"{self.base_url}/v2/booking/{rid}/slot_locks"
        
        payload = {
            "party_size": party_size,
            "date_time": date_time,
            "reservation_attribute": reservation_attribute
        }
        
        if experience:
            payload["experience"] = experience
        if dining_area_id:
            payload["dining_area_id"] = dining_area_id
        if environment:
            payload["environment"] = environment
        
        response = requests.post(url, json=payload, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def create_reservation(
        self,
        rid: int,
        reservation_token: str,
        first_name: str,
        last_name: str,
        email_address: str,
        phone: Dict[str, str],
        reservation_attribute: str = "default",
        special_request: Optional[str] = None,
        credit_card: Optional[Dict[str, str]] = None,
        restaurant_email_marketing_opt_in: Optional[str] = None,
        dining_area_id: Optional[str] = None,
        environment: Optional[str] = None,
        experience: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a reservation.
        
        Args:
            rid: Restaurant ID
            reservation_token: Token from slot lock
            first_name: First name
            last_name: Last name
            email_address: Email address
            phone: Phone number dict with number, country_code, phone_type
            reservation_attribute: Reservation attribute (default: "default")
            special_request: Special request (optional)
            credit_card: Credit card dict with token and last4 (optional)
            restaurant_email_marketing_opt_in: Marketing opt-in (optional)
            dining_area_id: Dining area ID (optional)
            environment: Environment (optional)
            experience: Experience details (optional)
        
        Returns:
            API response with confirmation details
        """
        url = f"{self.base_url}/v2/booking/{rid}/reservations"
        
        payload = {
            "reservation_token": reservation_token,
            "first_name": first_name,
            "last_name": last_name,
            "email_address": email_address,
            "phone": phone,
            "reservation_attribute": reservation_attribute
        }
        
        if special_request:
            payload["special_request"] = special_request
        if credit_card:
            payload["credit_card"] = credit_card
        if restaurant_email_marketing_opt_in:
            payload["restaurant_email_marketing_opt_in"] = restaurant_email_marketing_opt_in
        if dining_area_id:
            payload["dining_area_id"] = dining_area_id
        if environment:
            payload["environment"] = environment
        if experience:
            payload["experience"] = experience
        
        response = requests.post(url, json=payload, headers=self._get_headers(), timeout=30)
        response.raise_for_status()
        return response.json()
    
    def update_reservation(
        self,
        rid: int,
        confirmation_id: int,
        party_size: Optional[int] = None,
        date_time: Optional[str] = None,
        reservation_attribute: Optional[str] = None,
        reservation_token: Optional[str] = None,
        special_request: Optional[str] = None,
        experience: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update a reservation.
        
        Args:
            rid: Restaurant ID
            confirmation_id: Confirmation number
            party_size: Party size (optional)
            date_time: New date and time (optional)
            reservation_attribute: Reservation attribute (optional)
            reservation_token: Reservation token (optional)
            special_request: Special request (optional)
            experience: Experience details (optional)
        
        Returns:
            API response with updated reservation details
        """
        url = f"{self.base_url}/v2/booking/{rid}/reservations/{rid}-{confirmation_id}"
        
        payload = {}
        
        if party_size is not None:
            payload["party_size"] = party_size
        if date_time:
            payload["date_time"] = date_time
        if reservation_attribute:
            payload["reservation_attribute"] = reservation_attribute
        if reservation_token:
            payload["reservation_token"] = reservation_token
        if special_request:
            payload["special_request"] = special_request
        if experience:
            payload["experience"] = experience
        
        response = requests.put(url, json=payload, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def cancel_reservation(
        self,
        rid: int,
        confirmation_id: int
    ) -> bool:
        """
        Cancel a reservation.
        
        Args:
            rid: Restaurant ID
            confirmation_id: Confirmation number
        
        Returns:
            True if successful
        """
        url = f"{self.base_url}/v2/booking/{rid}/reservations/{rid}-{confirmation_id}"
        
        payload = {
            "status": "CancelledWeb"
        }
        
        response = requests.put(url, json=payload, headers=self._get_headers())
        response.raise_for_status()
        # Successful cancellation returns 200 OK with empty body
        return response.status_code == 200


