"""
OpenTable Service for handling OpenTable API operations and logging.
"""
from typing import Dict, Optional, Any
import json
from app.integrations.opentable_client import OpenTableClient
from app.repositories.mysql_opentable_log_repo import MySQLOpenTableLogRepository
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository


class OpenTableService:
    """Service for OpenTable operations."""

    def __init__(self):
        self.log_repo = MySQLOpenTableLogRepository()
        self.restaurant_repo = MySQLRestaurantRepository()

    def _get_restaurant_opentable_config(self, restaurant_id: int) -> Dict[str, Any]:
        """
        Get OpenTable configuration for a restaurant.

        Args:
            restaurant_id: Restaurant ID

        Returns:
            Dictionary with base_url and bearer_token
        """
        restaurant = self.restaurant_repo.get_by_id(restaurant_id)
        if not restaurant:
            raise ValueError(f"Restaurant with ID {restaurant_id} not found")

        open_table_details = restaurant.get('open_table_details')
        if not open_table_details:
            raise ValueError(f"OpenTable configuration not found for restaurant {restaurant_id}")

        # If it's a string, parse it as JSON
        if isinstance(open_table_details, str):
            open_table_details = json.loads(open_table_details)

        base_url = open_table_details.get('base_url')
        bearer_token = open_table_details.get('bearer_token')

        if not base_url or not bearer_token:
            raise ValueError(f"OpenTable base_url or bearer_token not configured for restaurant {restaurant_id}")

        return {
            'base_url': base_url,
            'bearer_token': bearer_token
        }

    def _log_api_call(
        self,
        restaurant_id: int,
        endpoint: str,
        method: str,
        request_payload: Optional[Dict] = None,
        response_payload: Optional[Dict] = None,
        status_code: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> int:
        """
        Log an API call to the database.

        Args:
            restaurant_id: Restaurant ID
            endpoint: API endpoint
            method: HTTP method
            request_payload: Request payload
            response_payload: Response payload
            status_code: HTTP status code
            error_message: Error message if any

        Returns:
            Log ID
        """
        return self.log_repo.create_log(
            restaurant_id=restaurant_id,
            endpoint=endpoint,
            method=method,
            request_payload=request_payload,
            response_payload=response_payload,
            status_code=status_code,
            error_message=error_message
        )

    def get_availability(
        self,
        restaurant_id: int,
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
            restaurant_id: Internal restaurant ID
            rid: OpenTable restaurant ID
            start_date_time: Start date and time
            forward_minutes: Forward booking window
            backward_minutes: Backward booking window
            party_size: Party size
            require_attributes: Table types
            include_credit_card_results: Include credit card results
            include_experiences: Include experiences

        Returns:
            Availability response
        """
        endpoint = f"/v2/availability/{rid}"
        request_payload = {
            "start_date_time": start_date_time,
            "forward_minutes": forward_minutes,
            "backward_minutes": backward_minutes,
            "party_size": party_size,
            "require_attributes": require_attributes,
            "include_credit_card_results": include_credit_card_results,
            "include_experiences": include_experiences
        }

        try:
            config = self._get_restaurant_opentable_config(restaurant_id)
            client = OpenTableClient(
                base_url=config['base_url'],
                bearer_token=config['bearer_token']
            )

            response = client.get_availability(
                rid=rid,
                start_date_time=start_date_time,
                forward_minutes=forward_minutes,
                backward_minutes=backward_minutes,
                party_size=party_size,
                require_attributes=require_attributes,
                include_credit_card_results=include_credit_card_results,
                include_experiences=include_experiences
            )

            self._log_api_call(
                restaurant_id=restaurant_id,
                endpoint=endpoint,
                method="GET",
                request_payload=request_payload,
                response_payload=response,
                status_code=200
            )

            return response

        except Exception as e:
            error_message = str(e)
            self._log_api_call(
                restaurant_id=restaurant_id,
                endpoint=endpoint,
                method="GET",
                request_payload=request_payload,
                status_code=None,
                error_message=error_message
            )
            raise

    def lock_slot(
        self,
        restaurant_id: int,
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
            restaurant_id: Internal restaurant ID
            rid: OpenTable restaurant ID
            party_size: Party size
            date_time: Date and time
            reservation_attribute: Reservation attribute
            experience: Experience details
            dining_area_id: Dining area ID
            environment: Environment

        Returns:
            Slot lock response with reservation_token
        """
        endpoint = f"/v2/booking/{rid}/slot_locks"
        request_payload = {
            "party_size": party_size,
            "date_time": date_time,
            "reservation_attribute": reservation_attribute,
            "experience": experience,
            "dining_area_id": dining_area_id,
            "environment": environment
        }

        try:
            config = self._get_restaurant_opentable_config(restaurant_id)
            client = OpenTableClient(
                base_url=config['base_url'],
                bearer_token=config['bearer_token']
            )

            response = client.lock_slot(
                rid=rid,
                party_size=party_size,
                date_time=date_time,
                reservation_attribute=reservation_attribute,
                experience=experience,
                dining_area_id=dining_area_id,
                environment=environment
            )

            self._log_api_call(
                restaurant_id=restaurant_id,
                endpoint=endpoint,
                method="POST",
                request_payload=request_payload,
                response_payload=response,
                status_code=200
            )

            return response

        except Exception as e:
            error_message = str(e)
            self._log_api_call(
                restaurant_id=restaurant_id,
                endpoint=endpoint,
                method="POST",
                request_payload=request_payload,
                status_code=None,
                error_message=error_message
            )
            raise

    def create_reservation(
        self,
        restaurant_id: int,
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
            restaurant_id: Internal restaurant ID
            rid: OpenTable restaurant ID
            reservation_token: Token from slot lock
            first_name: First name
            last_name: Last name
            email_address: Email address
            phone: Phone number dict
            reservation_attribute: Reservation attribute
            special_request: Special request
            credit_card: Credit card dict
            restaurant_email_marketing_opt_in: Marketing opt-in
            dining_area_id: Dining area ID
            environment: Environment
            experience: Experience details

        Returns:
            Reservation response with confirmation_number
        """
        endpoint = f"/v2/booking/{rid}/reservations"
        request_payload = {
            "reservation_token": reservation_token,
            "first_name": first_name,
            "last_name": last_name,
            "email_address": email_address,
            "phone": phone,
            "reservation_attribute": reservation_attribute,
            "special_request": special_request,
            "credit_card": credit_card,
            "restaurant_email_marketing_opt_in": restaurant_email_marketing_opt_in,
            "dining_area_id": dining_area_id,
            "environment": environment,
            "experience": experience
        }

        try:
            config = self._get_restaurant_opentable_config(restaurant_id)
            client = OpenTableClient(
                base_url=config['base_url'],
                bearer_token=config['bearer_token']
            )

            response = client.create_reservation(
                rid=rid,
                reservation_token=reservation_token,
                first_name=first_name,
                last_name=last_name,
                email_address=email_address,
                phone=phone,
                reservation_attribute=reservation_attribute,
                special_request=special_request,
                credit_card=credit_card,
                restaurant_email_marketing_opt_in=restaurant_email_marketing_opt_in,
                dining_area_id=dining_area_id,
                environment=environment,
                experience=experience
            )

            self._log_api_call(
                restaurant_id=restaurant_id,
                endpoint=endpoint,
                method="POST",
                request_payload=request_payload,
                response_payload=response,
                status_code=200
            )

            return response

        except Exception as e:
            error_message = str(e)
            self._log_api_call(
                restaurant_id=restaurant_id,
                endpoint=endpoint,
                method="POST",
                request_payload=request_payload,
                status_code=None,
                error_message=error_message
            )
            raise

    def update_reservation(
        self,
        restaurant_id: int,
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
            restaurant_id: Internal restaurant ID
            rid: OpenTable restaurant ID
            confirmation_id: Confirmation number
            party_size: Party size
            date_time: New date and time
            reservation_attribute: Reservation attribute
            reservation_token: Reservation token
            special_request: Special request
            experience: Experience details

        Returns:
            Updated reservation response
        """
        endpoint = f"/v2/booking/{rid}/reservations/{rid}-{confirmation_id}"
        request_payload = {
            "party_size": party_size,
            "date_time": date_time,
            "reservation_attribute": reservation_attribute,
            "reservation_token": reservation_token,
            "special_request": special_request,
            "experience": experience
        }

        try:
            config = self._get_restaurant_opentable_config(restaurant_id)
            client = OpenTableClient(
                base_url=config['base_url'],
                bearer_token=config['bearer_token']
            )

            response = client.update_reservation(
                rid=rid,
                confirmation_id=confirmation_id,
                party_size=party_size,
                date_time=date_time,
                reservation_attribute=reservation_attribute,
                reservation_token=reservation_token,
                special_request=special_request,
                experience=experience
            )

            self._log_api_call(
                restaurant_id=restaurant_id,
                endpoint=endpoint,
                method="PUT",
                request_payload=request_payload,
                response_payload=response,
                status_code=200
            )

            return response

        except Exception as e:
            error_message = str(e)
            self._log_api_call(
                restaurant_id=restaurant_id,
                endpoint=endpoint,
                method="PUT",
                request_payload=request_payload,
                status_code=None,
                error_message=error_message
            )
            raise

    def cancel_reservation(
        self,
        restaurant_id: int,
        rid: int,
        confirmation_id: int
    ) -> Dict[str, Any]:
        """
        Cancel a reservation.

        Args:
            restaurant_id: Internal restaurant ID
            rid: OpenTable restaurant ID
            confirmation_id: Confirmation number

        Returns:
            Success response
        """
        endpoint = f"/v2/booking/{rid}/reservations/{rid}-{confirmation_id}"
        request_payload = {
            "status": "CancelledWeb"
        }

        try:
            config = self._get_restaurant_opentable_config(restaurant_id)
            client = OpenTableClient(
                base_url=config['base_url'],
                bearer_token=config['bearer_token']
            )

            success = client.cancel_reservation(
                rid=rid,
                confirmation_id=confirmation_id
            )

            response_payload = {"success": success, "message": "Reservation cancelled successfully"}

            self._log_api_call(
                restaurant_id=restaurant_id,
                endpoint=endpoint,
                method="PUT",
                request_payload=request_payload,
                response_payload=response_payload,
                status_code=200
            )

            return response_payload

        except Exception as e:
            error_message = str(e)
            self._log_api_call(
                restaurant_id=restaurant_id,
                endpoint=endpoint,
                method="PUT",
                request_payload=request_payload,
                status_code=None,
                error_message=error_message
            )
            raise
