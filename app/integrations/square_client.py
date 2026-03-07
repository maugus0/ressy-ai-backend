import json
from typing import Any, Dict, List, Optional

import requests

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class SquareClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = settings.SQUARE_API_BASE_URL

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Square-Version": "2026-01-22",
        }

    def create_order(
        self, location_id: str, order_data: Dict[str, Any], idempotency_key: str, currency: str = "USD"
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v2/orders"
        # Square API requires the order data to be wrapped in an "order" object
        order_payload = {
            "location_id": location_id,
            "line_items": order_data.get("line_items", []),
        }
        if order_data.get("fulfillments"):
            order_payload["fulfillments"] = order_data.get("fulfillments")
        if order_data.get("reference_id"):
            order_payload["reference_id"] = order_data.get("reference_id")

        payload = {
            "idempotency_key": idempotency_key,
            "order": order_payload,
        }
        headers = self._get_headers()
        line_items_count = len(order_payload.get("line_items", []))
        logger.info(
            f"[Square API] Creating order: location_id={location_id}, idempotency_key={idempotency_key}, line_items={line_items_count}"
        )
        logger.debug(f"[Square API] Request URL: {url}")
        logger.debug(f"[Square API] Request payload: {json.dumps(payload, indent=2)}")

        # Log curl command for debugging (with masked authorization token)
        auth_token = headers.get("Authorization", "").replace("Bearer ", "")
        # Avoid logging the full bearer token; show only a small, non-sensitive portion
        if auth_token:
            masked_token = f"{auth_token[:6]}...{auth_token[-4:]}" if len(auth_token) > 10 else "***masked***"
        else:
            masked_token = "***no-token***"
        payload_json = json.dumps(payload)
        curl_command = f"""curl {url} \\
  -X POST \\
  -H 'Square-Version: {headers.get("Square-Version", "")}' \\
  -H 'Authorization: Bearer {masked_token}' \\
  -H 'Content-Type: {headers.get("Content-Type", "")}' \\
  -d '{payload_json}'"""
        logger.info("[Square API] Equivalent curl command (authorization token masked):")
        logger.info(curl_command)
        try:
            logger.info("[Square API] Sending POST request to Square API...")
            logger.info(f"[Square API] Complete request body: {json.dumps(payload, indent=2)}")
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            logger.info(f"[Square API] Response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            logger.info(
                f"[Square API] Order creation successful! Response keys: {list(result.keys()) if result else 'None'}"
            )
            if result.get("order"):
                order_id = result["order"].get("id")
                logger.info(f"[Square API] Square order ID: {order_id}")
            logger.debug(f"[Square API] Full response: {json.dumps(result, indent=2)}")
            return result
        except requests.exceptions.Timeout as e:
            logger.error(f"[Square API] Timeout error after 30s: {e}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[Square API] Connection error (network issue): {e}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"[Square API] HTTP error: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"[Square API] Error status code: {e.response.status_code}")
                try:
                    error_body = e.response.json()
                    logger.error(f"[Square API] Error response body: {json.dumps(error_body, indent=2)}")
                except (ValueError, AttributeError):
                    logger.error(f"[Square API] Error response text: {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"[Square API] Request exception: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"[Square API] Response text: {e.response.text}")
            raise
        except Exception as e:
            logger.exception(f"[Square API] Unexpected error: {e}")
            raise

    def list_catalog(self, types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        List catalog objects from Square.
        
        Args:
            types: Optional list of catalog object types to filter (e.g., ["ITEM", "MODIFIER_LIST"])
                  If None, returns all types. Note: Square's /v2/catalog/list endpoint doesn't support
                  filtering by types in the request - it returns all catalog objects.
        
        Returns:
            The Square API catalog response with objects array
        """
        url = f"{self.base_url}/v2/catalog/list"
        headers = self._get_headers()
        
        logger.info(f"[Square API] Listing catalog: types={types if types else 'all (no filter)'}")
        logger.debug(f"[Square API] Catalog request URL: {url}")
        logger.info(
            "[Square API] Note: Square /v2/catalog/list returns all catalog objects. "
            "Filtering by types will be done client-side if types parameter is provided."
        )
        
        # Log curl command for debugging (with masked authorization token)
        auth_token = headers.get("Authorization", "").replace("Bearer ", "")
        if auth_token:
            masked_token = f"{auth_token[:6]}...{auth_token[-4:]}" if len(auth_token) > 10 else "***masked***"
        else:
            masked_token = "***no-token***"
        
        curl_command = f"""curl {url} \\
  -H 'Square-Version: {headers.get("Square-Version", "")}' \\
  -H 'Authorization: Bearer {masked_token}' \\
  -H 'Content-Type: {headers.get("Content-Type", "")}'"""
        logger.info("[Square API] Equivalent curl command (authorization token masked):")
        logger.info(curl_command)
        
        try:
            logger.info("[Square API] Sending GET request to Square Catalog List API...")
            response = requests.get(url, headers=headers, timeout=30)
            logger.info(f"[Square API] Catalog response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            all_objects = result.get("objects", [])
            objects_count = len(all_objects)
            
            # Filter by types if specified (client-side filtering since API doesn't support it)
            if types:
                filtered_objects = [obj for obj in all_objects if obj.get("type") in types]
                result["objects"] = filtered_objects
                logger.info(
                    f"[Square API] Catalog listing successful! Found {len(filtered_objects)} objects "
                    f"(filtered from {objects_count} total) matching types: {types}"
                )
            else:
                logger.info(
                    f"[Square API] Catalog listing successful! Found {objects_count} catalog objects. "
                    f"Response keys: {list(result.keys()) if result else 'None'}"
                )
            
            logger.debug(f"[Square API] Full catalog response: {json.dumps(result, indent=2)}")
            return result
        except requests.exceptions.Timeout as e:
            logger.error(f"[Square API] Catalog timeout error after 30s: {e}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[Square API] Catalog connection error (network issue): {e}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"[Square API] Catalog HTTP error: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"[Square API] Catalog error status code: {e.response.status_code}")
                try:
                    error_body = e.response.json()
                    logger.error(f"[Square API] Catalog error response body: {json.dumps(error_body, indent=2)}")
                except (ValueError, AttributeError):
                    logger.error(f"[Square API] Catalog error response text: {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"[Square API] Catalog request exception: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"[Square API] Catalog response text: {e.response.text}")
            raise
        except Exception as e:
            logger.exception(f"[Square API] Catalog unexpected error: {e}")
            raise

    def create_payment(
        self, order_id: str, amount: float, currency: str, idempotency_key: str
    ) -> Dict[str, Any]:
        """
        Create a cash payment for a Square order.
        
        Args:
            order_id: The Square order ID from the create_order response
            amount: The payment amount (in dollars, will be converted to cents)
            currency: The currency code (e.g., "USD")
            idempotency_key: Unique key for idempotency
            
        Returns:
            The Square API payment response
        """
        url = f"{self.base_url}/v2/payments"
        amount_cents = int(amount * 100)  # Convert to cents for Square API
        
        payload = {
            "idempotency_key": idempotency_key,
            "source_id": "CASH",
            "order_id": order_id,
            "amount_money": {
                "amount": amount_cents,
                "currency": currency,
            },
            "cash_details": {
                "buyer_supplied_money": {
                    "amount": amount_cents,
                    "currency": currency,
                }
            },
        }
        headers = self._get_headers()
        
        logger.info(
            f"[Square API] Creating payment: order_id={order_id}, amount={amount_cents} cents ({currency}), idempotency_key={idempotency_key}"
        )
        logger.debug(f"[Square API] Payment request URL: {url}")
        logger.debug(f"[Square API] Payment request payload: {json.dumps(payload, indent=2)}")
        
        # Log curl command for debugging (with masked authorization token)
        auth_token = headers.get("Authorization", "").replace("Bearer ", "")
        if auth_token:
            masked_token = f"{auth_token[:6]}...{auth_token[-4:]}" if len(auth_token) > 10 else "***masked***"
        else:
            masked_token = "***no-token***"
        payload_json = json.dumps(payload)
        curl_command = f"""curl {url} \\
  -X POST \\
  -H 'Square-Version: {headers.get("Square-Version", "")}' \\
  -H 'Authorization: Bearer {masked_token}' \\
  -H 'Content-Type: {headers.get("Content-Type", "")}' \\
  -d '{payload_json}'"""
        logger.info("[Square API] Equivalent curl command for payment (authorization token masked):")
        logger.info(curl_command)
        
        try:
            logger.info("[Square API] Sending POST request to Square Payments API...")
            logger.info(f"[Square API] Complete payment request body: {json.dumps(payload, indent=2)}")
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            logger.info(f"[Square API] Payment response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            logger.info(
                f"[Square API] Payment creation successful! Response keys: {list(result.keys()) if result else 'None'}"
            )
            if result.get("payment"):
                payment_id = result["payment"].get("id")
                logger.info(f"[Square API] Square payment ID: {payment_id}")
            logger.debug(f"[Square API] Full payment response: {json.dumps(result, indent=2)}")
            return result
        except requests.exceptions.Timeout as e:
            logger.error(f"[Square API] Payment timeout error after 30s: {e}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[Square API] Payment connection error (network issue): {e}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"[Square API] Payment HTTP error: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"[Square API] Payment error status code: {e.response.status_code}")
                try:
                    error_body = e.response.json()
                    logger.error(f"[Square API] Payment error response body: {json.dumps(error_body, indent=2)}")
                except (ValueError, AttributeError):
                    logger.error(f"[Square API] Payment error response text: {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"[Square API] Payment request exception: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"[Square API] Payment response text: {e.response.text}")
            raise
        except Exception as e:
            logger.exception(f"[Square API] Payment unexpected error: {e}")
            raise

