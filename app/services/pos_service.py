import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.config import settings
from app.integrations.square_client import SquareClient
from app.integrations.toast_client import ToastClient
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_order_pos_sync_repo import MySQLOrderPOSSyncRepository
from app.repositories.mysql_order_repo import MySQLOrderRepository
from app.repositories.mysql_pos_integration_repo import MySQLPOSIntegrationRepository
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository
from app.services.menu_pos_mapping_service import MenuPOSMappingService
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class POSService:
    def __init__(self):
        self.pos_integration_repo = MySQLPOSIntegrationRepository()
        self.order_sync_repo = MySQLOrderPOSSyncRepository()
        self.order_repo = MySQLOrderRepository()
        self.menu_repo = MySQLMenuRepository()
        self.menu_mapping_service = MenuPOSMappingService()
        self.restaurant_repo = MySQLRestaurantRepository()

    def _get_item_price(self, item: Dict, menu_repo: MySQLMenuRepository) -> float:
        # Priority 1: Use price from order_details (actual price at time of order)
        if item.get("price") is not None:
            price = float(item["price"])
            logger.debug(f"Using price from order_details for '{item.get('name')}': ${price:.2f}")
            return price
        # Priority 2: Lookup from menu if item_id exists
        if item.get("item_id"):
            menu_item = menu_repo.get_by_id(item["item_id"])
            if menu_item:
                price = float(menu_item.get("price", 0))
                logger.debug(
                    f"Using price from menu lookup for '{item.get('name')}' (item_id={item.get('item_id')}): ${price:.2f}"
                )
                return price
        # Priority 3: Fallback to 0.00 (should not happen in normal flow)
        logger.warning(f"No price found for item: {item.get('name')} (item_id={item.get('item_id')}), using $0.00")
        return 0.00

    def _sync_to_square(
        self,
        order_id: int,
        pos_integration: Dict,
        order_data: Dict,
        idempotency_key: str,
        order: Optional[Dict] = None,
        customization: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        access_token = pos_integration.get("credentials", {}).get("access_token")
        if not access_token:
            access_token = settings.SQUARE_ACCESS_TOKEN
            if not access_token:
                logger.error(f"Square access token not found for order {order_id}")
                raise ValueError("Square access token not found in credentials or environment")
            logger.info(f"Using Square access token from environment for order {order_id}")

        location_id = pos_integration.get("location_id")
        if not location_id or location_id.strip() == "":
            logger.error(
                f"Square location_id not configured for order {order_id}, integration_id: {pos_integration.get('id')}"
            )
            raise ValueError(
                "Square location_id not configured. Please configure location_id in POS integration settings."
            )

        logger.info(f"[POS Sync] Syncing order {order_id} to Square POS, location_id: {location_id}")
        square_client = SquareClient(access_token)

        # Get currency from integration or default to USD
        currency = pos_integration.get("currency") or "USD"
        if not currency or currency.strip() == "":
            currency = "USD"
        logger.info(f"[POS Sync] Using currency: {currency}")

        # Check if we should use Square catalog (custom: false) or ad-hoc items (custom: true or not set)
        # Get restaurant_id from order or pos_integration
        restaurant_id = order.get("restaurant_id") if order else None
        if not restaurant_id:
            # Try to get from pos_integration if available
            restaurant_id = pos_integration.get("restaurant_id")
        
        use_catalog = False
        if restaurant_id:
            restaurant = self.restaurant_repo.get_by_id(restaurant_id)
            if restaurant:
                pos_flags = restaurant.get("pos_integration_flags")
                if isinstance(pos_flags, str):
                    try:
                        pos_flags = json.loads(pos_flags)
                    except (json.JSONDecodeError, TypeError):
                        pos_flags = {}
                elif pos_flags is None:
                    pos_flags = {}
                
                # Check if custom flag is explicitly set to false
                # Default to True (use ad-hoc) if not specified
                use_catalog = pos_flags.get("custom") is False
                logger.info(
                    f"[POS Sync] Restaurant {restaurant_id} pos_integration_flags: {pos_flags}, "
                    f"use_catalog (custom=False): {use_catalog}"
                )
        
        line_items = []
        order_details = order_data.get("order_details", [])
        logger.info(
            f"[POS Sync] Converting {len(order_details)} order items to Square line_items "
            f"(use_catalog={use_catalog})"
        )
        
        pos_integration_id = pos_integration.get("id")
        
        for idx, item in enumerate(order_details):
            menu_item_id = item.get("item_id")
            quantity = str(item.get("quantity", 1))
            item_name = item.get("name", "Unknown Item")
            catalog_object_id = None
            
            # Try to use catalog if enabled and we have the necessary IDs
            if use_catalog and menu_item_id and pos_integration_id:
                # Use Square catalog: get catalog_object_id (variation_id) from menu_pos_mapping
                catalog_object_id = self.menu_mapping_service.get_pos_menu_item_id(menu_item_id, pos_integration_id)
                
                if catalog_object_id:
                    # Create line item using catalog_object_id (recommended approach)
                    line_item = {
                        "catalog_object_id": catalog_object_id,
                        "quantity": quantity,
                    }
                    
                    # Add modifiers if any (could be extended in future)
                    # For now, instructions go as note
                    if item.get("instructions"):
                        # Note: Square catalog items can have modifiers, but we'll use note for instructions
                        # In future, we could map instructions to Square modifiers
                        logger.debug(
                            f"[POS Sync] Item {item_name} has instructions, but using catalog_object_id. "
                            f"Instructions: {item.get('instructions')}"
                        )
                    
                    line_items.append(line_item)
                    logger.info(
                        f"[POS Sync] Line item {idx+1} (catalog): {item_name} x{quantity} "
                        f"(catalog_object_id={catalog_object_id})"
                    )
                    continue  # Skip ad-hoc creation for this item
            
            # Use ad-hoc line items (custom: true, no mapping found, or catalog not enabled)
            if not catalog_object_id:
                # Get price from order_details (price at time of order) or fallback to menu
                price = self._get_item_price(item, self.menu_repo)
                price_source = (
                    "order_details" if item.get("price") is not None else ("menu" if item.get("item_id") else "fallback")
                )
                amount_cents = int(price * 100)  # Convert to cents for Square API
                line_item = {
                    "quantity": quantity,
                    "item_type": "ITEM",
                    "name": item_name,
                    "base_price_money": {
                        "amount": amount_cents,
                        "currency": currency,
                    },
                }
                if item.get("instructions"):
                    line_item["note"] = item.get("instructions")[:500]
                line_items.append(line_item)
                
                if use_catalog and menu_item_id:
                    logger.warning(
                        f"[POS Sync] Line item {idx+1} (ad-hoc fallback): {item_name} x{quantity} "
                        f"@ ${price:.2f} ({currency}) - No catalog mapping found for menu_item_id={menu_item_id}"
                    )
                else:
                    logger.info(
                        f"[POS Sync] Line item {idx+1} (ad-hoc): {line_item['name']} x{line_item['quantity']} "
                        f"@ ${price:.2f} ({currency}) - Price source: {price_source}, Amount (cents): {amount_cents}"
                    )

        # Build pickup_details with recipient information
        pickup_details = {}
        customer_phone = order_data.get("customer_phone", "").strip() if order_data.get("customer_phone") else ""
        customer_name = order_data.get("customer_name", "").strip() if order_data.get("customer_name") else ""

        # Calculate pickup_at time
        pickup_time_iso = None
        if customization and isinstance(customization, dict):
            pickup_time_iso = customization.get("pickup_time_iso") or customization.get("pickup_time")

        # If not in customization, calculate based on created_at + average prep time
        if not pickup_time_iso and order:
            order_created_at = order.get("created_at")
            if order_created_at:
                # Parse created_at if it's a string
                if isinstance(order_created_at, str):
                    try:
                        order_created_at = datetime.fromisoformat(order_created_at.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        order_created_at = datetime.now(timezone.utc)
                elif not isinstance(order_created_at, datetime):
                    order_created_at = datetime.now(timezone.utc)

                # Calculate average prep time from order items
                total_prep_minutes = 0
                item_count = 0
                order_details_list = order_data.get("order_details", [])

                for item in order_details_list:
                    item_id = item.get("item_id")
                    quantity = item.get("quantity", 1)
                    if item_id:
                        menu_item = self.menu_repo.get_by_id(item_id)
                        if menu_item and menu_item.get("avg_prep_time"):
                            prep_time = float(menu_item.get("avg_prep_time", 0))
                            total_prep_minutes += prep_time * quantity
                            item_count += quantity

                # Determine default prep time from settings, fallback to 20 minutes
                default_prep_minutes = settings.DEFAULT_PREP_TIME_MINUTES
                # If no prep times found in menu items or no items counted, use default
                if total_prep_minutes == 0 or item_count == 0:
                    avg_prep_minutes = default_prep_minutes
                else:
                    avg_prep_minutes = total_prep_minutes / item_count

                # Calculate pickup time: created_at + prep time
                pickup_datetime = order_created_at + timedelta(minutes=avg_prep_minutes)

                # Ensure timezone-aware (UTC)
                if pickup_datetime.tzinfo is None:
                    pickup_datetime = pickup_datetime.replace(tzinfo=timezone.utc)
                else:
                    pickup_datetime = pickup_datetime.astimezone(timezone.utc)

                # Format as ISO 8601 with Z timezone
                pickup_time_iso = pickup_datetime.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                logger.info(
                    f"[POS Sync] Calculated pickup_at: {pickup_time_iso} (prep_time: {avg_prep_minutes:.1f} minutes)"
                )
            else:
                # Fallback: use current time + default prep time
                default_prep_minutes = settings.DEFAULT_PREP_TIME_MINUTES
                pickup_datetime = datetime.now(timezone.utc) + timedelta(minutes=default_prep_minutes)
                pickup_time_iso = pickup_datetime.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                logger.warning(
                    f"[POS Sync] Order created_at not available, using current time + {default_prep_minutes} min: {pickup_time_iso}"
                )

        # Phone numbers should already be in E.164 format from the database
        # But ensure it starts with + for Square API (E.164 format requirement)
        if customer_phone and not customer_phone.startswith("+"):
            # If phone doesn't start with +, try to format it
            # Remove any non-digit characters except +
            digits_only = re.sub(r"[^\d]", "", customer_phone)
            if len(digits_only) == 10:
                # 10 digits - assume US/Canada, add +1
                customer_phone = f"+1{digits_only}"
            elif len(digits_only) == 11 and digits_only.startswith("1"):
                # 11 digits starting with 1 - add +
                customer_phone = f"+{digits_only}"
            elif digits_only:
                # Other format - try to add + prefix
                customer_phone = f"+{digits_only}"

        # Build recipient object if we have phone number
        if customer_phone:
            recipient = {"phone_number": customer_phone}
            # Add display_name if customer name is available
            if customer_name:
                recipient["display_name"] = customer_name

            pickup_details["recipient"] = recipient
            logger.info(
                f"[POS Sync] Added pickup_details recipient: phone={customer_phone}, display_name={customer_name if customer_name else 'N/A'}"
            )
        else:
            logger.warning("[POS Sync] No customer phone number available for pickup_details recipient")

        # Add pickup_at time if calculated
        if pickup_time_iso:
            pickup_details["pickup_at"] = pickup_time_iso

        # Square API fulfillment with pickup_details
        fulfillment = {"type": "PICKUP", "pickup_details": pickup_details}

        square_order_data = {
            "line_items": line_items,
            "fulfillments": [fulfillment],
            "reference_id": f"RESSY-{order_id}",
        }

        logger.info(
            f"[POS Sync] Square order payload for order {order_id}: {len(line_items)} line_items, fulfillment: PICKUP, currency: {currency}"
        )
        logger.debug(f"[POS Sync] Square order payload JSON: {json.dumps(square_order_data, indent=2)}")
        try:
            logger.info(f"[POS Sync] Calling Square API create_order for order {order_id}")
            response = square_client.create_order(location_id, square_order_data, idempotency_key, currency)
            logger.info(f"[POS Sync] Successfully synced order {order_id} to Square POS. Response received.")
            logger.debug(f"[POS Sync] Square API response: {json.dumps(response, indent=2) if response else 'None'}")
            return response
        except Exception as e:
            logger.error(f"[POS Sync] Failed to sync order {order_id} to Square POS: {str(e)}")
            logger.exception(f"[POS Sync] Square API error details for order {order_id}:")
            raise

    def _sync_to_toast(
        self, order_id: int, pos_integration: Dict, order_data: Dict, idempotency_key: str
    ) -> Dict[str, Any]:
        access_token = pos_integration.get("credentials", {}).get("access_token")
        if not access_token:
            raise ValueError("Toast access token not found in credentials")
        location_id = pos_integration.get("location_id")
        if not location_id:
            raise ValueError("Toast restaurant external ID not configured")

        toast_client = ToastClient(access_token)
        order_items = []
        for item in order_data.get("order_details", []):
            pos_menu_item_id = None
            if item.get("item_id"):
                pos_menu_item_id = self.menu_mapping_service.get_pos_menu_item_id(
                    item["item_id"], pos_integration["id"]
                )
            if not pos_menu_item_id:
                logger.warning(f"No Toast mapping found for menu item {item.get('item_id')} ({item.get('name')})")
                continue
            order_item = {
                "guid": pos_menu_item_id,
                "quantity": item.get("quantity", 1),
            }
            if item.get("instructions"):
                order_item["note"] = item.get("instructions")[:500]
            order_items.append(order_item)

        if not order_items:
            raise ValueError("No valid menu item mappings found for Toast order")

        prices_request = {"items": order_items, "diningOption": "TAKEOUT"}
        prices_response = toast_client.get_prices(location_id, prices_request)

        customer_name = order_data.get("customer_name", "Guest")
        customer_email = order_data.get("customer_email", "")
        customer_phone = order_data.get("customer_phone", "")

        name_parts = customer_name.split() if customer_name else ["Guest"]
        first_name = name_parts[0]
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        toast_order_data = {
            "items": order_items,
            "diningOption": "TAKEOUT",
            "guest": {
                "firstName": first_name,
                "lastName": last_name,
                "email": customer_email,
                "phone": customer_phone,
            },
        }

        response = toast_client.create_order(location_id, toast_order_data, prices_response)
        return response

    def _ensure_square_integration(self, restaurant_id: int) -> Optional[Dict]:
        restaurant = self.restaurant_repo.get_by_id(restaurant_id)
        if not restaurant:
            logger.warning(f"Restaurant {restaurant_id} not found for Square integration check")
            return None

        pos_flags = restaurant.get("pos_integration_flags")
        if isinstance(pos_flags, str):
            try:
                pos_flags = json.loads(pos_flags)
            except (json.JSONDecodeError, TypeError):
                pos_flags = {}

        square_enabled = pos_flags.get("square") if pos_flags else False
        if not square_enabled:
            logger.info(
                f"[POS Sync] Square POS not enabled in pos_integration_flags for restaurant {restaurant_id} (flags: {pos_flags})"
            )
            return None

        existing_integrations = self.pos_integration_repo.get_enabled_integrations(restaurant_id)
        logger.info(f"[POS Sync] Checking {len(existing_integrations)} existing integration(s) for Square")
        square_integration = next((pi for pi in existing_integrations if pi.get("pos_type") == "SQUARE"), None)

        if square_integration:
            logger.info(
                f"[POS Sync] Square integration found in database: id={square_integration.get('id')}, enabled={square_integration.get('enabled')}, location_id={square_integration.get('location_id')}"
            )
            return square_integration

        if not settings.SQUARE_ACCESS_TOKEN:
            logger.warning(f"Square POS enabled for restaurant {restaurant_id} but SQUARE_ACCESS_TOKEN not configured")
            return None

        if not settings.SQUARE_APPLICATION_ID:
            logger.warning(
                f"Square POS enabled for restaurant {restaurant_id} but SQUARE_APPLICATION_ID not configured in environment"
            )

        logger.info(
            f"Auto-creating Square integration for restaurant {restaurant_id} (location_id must be configured via API)"
        )
        integration_data = {
            "restaurant_id": restaurant_id,
            "pos_type": "SQUARE",
            "enabled": True,
            "credentials": {
                "access_token": settings.SQUARE_ACCESS_TOKEN,
                "application_id": settings.SQUARE_APPLICATION_ID,
            },
            "location_id": "",
            "currency": "USD",
            "default_order_options": {"dining_option": "PICKUP"},
        }
        try:
            integration_id = self.pos_integration_repo.create(integration_data)
            integration = self.pos_integration_repo.get_by_id(integration_id)
            logger.info(
                f"Created Square integration {integration_id} for restaurant {restaurant_id}. Note: location_id must be configured before orders can sync."
            )
            return integration
        except Exception as e:
            logger.error(f"Failed to create Square integration for restaurant {restaurant_id}: {str(e)}")
            return None

    def sync_order_to_pos(self, order_id: int, restaurant_id: int) -> None:
        try:
            logger.info(f"Starting POS sync for order {order_id}, restaurant {restaurant_id}")
            # Use get_order_with_user to get user details (phone, email) directly
            order = self.order_repo.get_order_with_user(order_id)
            if not order:
                logger.error(f"Order {order_id} not found for POS sync")
                return

            logger.info(f"[POS Sync] Fetching enabled POS integrations for restaurant {restaurant_id}")
            pos_integrations = self.pos_integration_repo.get_enabled_integrations(restaurant_id)
            logger.info(f"[POS Sync] Found {len(pos_integrations)} existing enabled integration(s) in database")

            logger.info(f"[POS Sync] Checking Square integration for restaurant {restaurant_id}")
            square_integration = self._ensure_square_integration(restaurant_id)
            if square_integration:
                logger.info(
                    f"[POS Sync] Square integration available: id={square_integration.get('id')}, enabled={square_integration.get('enabled')}, location_id={square_integration.get('location_id')}"
                )
                square_exists = any(pi.get("id") == square_integration.get("id") for pi in pos_integrations)
                if not square_exists:
                    pos_integrations.append(square_integration)
                    logger.info(f"[POS Sync] Added Square integration to sync list for order {order_id}")
                else:
                    logger.info("[POS Sync] Square integration already in enabled integrations list")
            else:
                logger.info(f"[POS Sync] No Square integration available for restaurant {restaurant_id}")

            if not pos_integrations:
                logger.warning(
                    f"[POS Sync] No enabled POS integrations found for restaurant {restaurant_id}, order {order_id}. POS sync skipped."
                )
                logger.warning(
                    "[POS Sync] To enable POS sync: 1) Set pos_integration_flags in Restaurants table, 2) Create POS_Integrations record with enabled=true"
                )
                return

            logger.info(
                f"[POS Sync] Processing {len(pos_integrations)} POS integration(s) for restaurant {restaurant_id}"
            )

            order_details = order.get("order_details", [])
            if isinstance(order_details, str):
                try:
                    order_details = json.loads(order_details)
                except (json.JSONDecodeError, TypeError):
                    order_details = []

            customization = order.get("customization", {})
            if isinstance(customization, str):
                try:
                    customization = json.loads(customization)
                except (json.JSONDecodeError, TypeError):
                    customization = {}

            # Get customer info from order (which includes user details from Users table)
            customer_name = order.get("customer_name") or customization.get("customer_name") or ""
            customer_phone = order.get("customer_phone") or customization.get("customer_phone") or ""
            customer_email = order.get("customer_email") or customization.get("customer_email") or ""
            user_id = order.get("user_id")  # Get user_id for Square customer_id

            order_data = {
                "order_details": order_details,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "customer_email": customer_email,
                "user_id": user_id,  # Include user_id for Square API
            }

            for pos_integration in pos_integrations:
                pos_type = pos_integration.get("pos_type")
                integration_id = pos_integration.get("id")
                enabled = pos_integration.get("enabled")
                location_id = pos_integration.get("location_id")
                idempotency_key = f"{order_id}-{integration_id}-{uuid.uuid4().hex[:8]}"

                logger.info(
                    f"[POS Sync] Processing {pos_type} integration: id={integration_id}, enabled={enabled}, location_id={location_id}"
                )
                logger.info(
                    f"[POS Sync] Syncing order {order_id} to {pos_type} POS (integration_id: {integration_id}, idempotency_key: {idempotency_key})"
                )

                sync_id = self.order_sync_repo.create_sync_record(
                    order_id, restaurant_id, integration_id, idempotency_key
                )

                try:
                    if pos_type == "SQUARE":
                        location_id = pos_integration.get("location_id")
                        if not location_id or location_id.strip() == "":
                            error_msg = "Square location_id not configured. Please configure location_id in POS integration settings."
                            logger.warning(f"[POS Sync] Skipping Square sync for order {order_id}: {error_msg}")
                            logger.warning(
                                f"[POS Sync] Integration details: id={integration_id}, enabled={enabled}, location_id='{location_id}'"
                            )
                            self.order_sync_repo.update_sync_status(
                                sync_id,
                                status="FAILED",
                                error=error_msg,
                                attempts=1,
                            )
                            continue

                        logger.info(
                            f"[POS Sync] Processing Square sync for order {order_id}, location_id: {location_id}"
                        )
                        logger.info(
                            f"[POS Sync] Order data: {len(order_data.get('order_details', []))} items, customer: {order_data.get('customer_name', 'N/A')}"
                        )
                        response = self._sync_to_square(
                            order_id, pos_integration, order_data, idempotency_key, order, customization
                        )
                        logger.info(f"[POS Sync] Square API response received for order {order_id}")
                        external_order_id = response.get("order", {}).get("id") if response.get("order") else None
                        if external_order_id:
                            logger.info(
                                f"[POS Sync] Order {order_id} successfully synced to Square, external_order_id: {external_order_id}"
                            )
                        else:
                            logger.warning(
                                f"[POS Sync] Order {order_id} synced to Square but no external_order_id in response. Response keys: {list(response.keys()) if response else 'None'}"
                            )
                        self.order_sync_repo.update_sync_status(
                            sync_id,
                            status="CONFIRMED",
                            external_order_id=external_order_id,
                            response_payload=response,
                        )
                        logger.info(f"[POS Sync] Updated sync record {sync_id} to CONFIRMED for order {order_id}")
                    elif pos_type == "TOAST":
                        logger.info(f"Processing Toast sync for order {order_id}")
                        response = self._sync_to_toast(order_id, pos_integration, order_data, idempotency_key)
                        external_order_id = response.get("guid") if response.get("guid") else None
                        if external_order_id:
                            logger.info(
                                f"Order {order_id} successfully synced to Toast, external_order_id: {external_order_id}"
                            )
                        else:
                            logger.warning(f"Order {order_id} synced to Toast but no external_order_id in response")
                        self.order_sync_repo.update_sync_status(
                            sync_id,
                            status="CONFIRMED",
                            external_order_id=external_order_id,
                            response_payload=response,
                        )
                    else:
                        logger.warning(f"Unknown POS type: {pos_type} for order {order_id}")
                        self.order_sync_repo.update_sync_status(
                            sync_id, status="FAILED", error=f"Unknown POS type: {pos_type}"
                        )
                except Exception as e:
                    error_msg = str(e)
                    logger.error(
                        f"POS sync failed for order {order_id}, POS {pos_type} (integration_id: {integration_id}): {error_msg}"
                    )
                    logger.exception(f"Exception details for order {order_id} POS sync failure:")
                    next_retry = datetime.now() + timedelta(minutes=settings.POS_RETRY_BASE_MINUTES)
                    self.order_sync_repo.update_sync_status(
                        sync_id,
                        status="PENDING",
                        error=error_msg,
                        attempts=1,
                        next_retry_at=next_retry,
                        request_payload=order_data,
                    )
                    logger.info(f"Scheduled retry for order {order_id} POS sync at {next_retry}")

            logger.info(f"[POS Sync] Completed POS sync processing for order {order_id}")
        except Exception as e:
            logger.exception(f"[POS Sync] Error in sync_order_to_pos for order {order_id}: {e}")
            logger.error(
                f"[POS Sync] POS sync failed completely for order {order_id}, restaurant {restaurant_id}: {str(e)}"
            )
