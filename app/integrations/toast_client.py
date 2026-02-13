from typing import Any, Dict, Optional

import requests

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class ToastClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = settings.TOAST_API_BASE_URL

    def _get_headers(self, restaurant_external_id: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        if restaurant_external_id:
            headers["Toast-Restaurant-External-ID"] = restaurant_external_id
        return headers

    def get_menus(self, restaurant_external_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/menus/v3/menus"
        headers = self._get_headers(restaurant_external_id)
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Toast Menus API error: {e}")
            if hasattr(e, "response") and e.response is not None and hasattr(e.response, "text"):
                logger.error(f"Toast Menus API response: {e.response.text}")
            raise

    def get_ordering_schedule(self, restaurant_external_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/ordering-schedule"
        headers = self._get_headers(restaurant_external_id)
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Toast Ordering Schedule API error: {e}")
            if hasattr(e, "response") and e.response is not None and hasattr(e.response, "text"):
                logger.error(f"Toast Ordering Schedule API response: {e.response.text}")
            raise

    def get_prices(self, restaurant_external_id: str, order_data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/prices"
        headers = self._get_headers(restaurant_external_id)
        try:
            response = requests.post(url, json=order_data, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Toast Prices API error: {e}")
            if hasattr(e, "response") and e.response is not None and hasattr(e.response, "text"):
                logger.error(f"Toast Prices API response: {e.response.text}")
            raise

    def create_order(
        self, restaurant_external_id: str, order_data: Dict[str, Any], prices_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/orders"
        payload = {
            **order_data,
            "prices": prices_response.get("prices", []),
        }
        headers = self._get_headers(restaurant_external_id)
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Toast Orders API error: {e}")
            if hasattr(e, "response") and e.response is not None and hasattr(e.response, "text"):
                logger.error(f"Toast Orders API response: {e.response.text}")
            raise
