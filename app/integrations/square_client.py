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
                  If None, returns all types
        
        Returns:
            The Square API catalog response with objects array
        """
        url = f"{self.base_url}/v2/catalog/list"
        headers = self._get_headers()
        
        payload = {}
        if types:
            payload["types"] = types
        
        logger.info(f"[Square API] Listing catalog: types={types if types else 'all'}")
        logger.debug(f"[Square API] Catalog request URL: {url}")
        if payload:
            logger.debug(f"[Square API] Catalog request payload: {json.dumps(payload, indent=2)}")
        
        # Log curl command for debugging (with masked authorization token)
        auth_token = headers.get("Authorization", "").replace("Bearer ", "")
        if auth_token:
            masked_token = f"{auth_token[:6]}...{auth_token[-4:]}" if len(auth_token) > 10 else "***masked***"
        else:
            masked_token = "***no-token***"
        
        # Build curl command
        curl_parts = [f"curl {url}"]
        curl_parts.append("-X POST" if payload else "-X GET")
        curl_parts.append(f"-H 'Square-Version: {headers.get('Square-Version', '')}'")
        curl_parts.append(f"-H 'Authorization: Bearer {masked_token}'")
        curl_parts.append(f"-H 'Content-Type: {headers.get('Content-Type', '')}'")
        if payload:
            payload_json = json.dumps(payload)
            curl_parts.append(f"-d '{payload_json}'")
        
        curl_command = " \\\n  ".join(curl_parts)
        logger.info("[Square API] Equivalent curl command (authorization token masked):")
        logger.info(curl_command)
        
        try:
            logger.info("[Square API] Sending request to Square Catalog API...")
            if payload:
                logger.info(f"[Square API] Complete catalog request body: {json.dumps(payload, indent=2)}")
                response = requests.post(url, json=payload, headers=headers, timeout=30)
            else:
                response = requests.get(url, headers=headers, timeout=30)
            logger.info(f"[Square API] Catalog response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            objects_count = len(result.get("objects", []))
            logger.info(
                f"[Square API] Catalog listing successful! Found {objects_count} catalog objects. Response keys: {list(result.keys()) if result else 'None'}"
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
