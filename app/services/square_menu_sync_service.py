"""
Service for syncing Square catalog menu to our menu table.
Used when creating restaurants to populate menu from Square.
"""

from typing import Any, Dict, List, Optional

from app.integrations.square_client import SquareClient
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class SquareMenuSyncService:
    """Service for syncing Square catalog items to our menu table."""

    def __init__(self):
        self.menu_repo = MySQLMenuRepository()

    def _flatten_square_catalog_items(self, catalog_response: Dict) -> List[Dict]:
        """
        Flatten Square catalog response to extract items (one entry per base item, not per variation).
        Uses only the base item name, ignoring variation names.
        Uses the first variation with a fixed price, or skips items with only variable pricing.
        """
        items = []
        catalog_objects = catalog_response.get("objects", [])
        
        for obj in catalog_objects:
            if obj.get("type") == "ITEM" and not obj.get("is_deleted", False):
                item_data = obj.get("item_data", {})
                item_id = obj.get("id")
                item_name = item_data.get("name", "").strip()
                item_description = item_data.get("description_plaintext") or item_data.get("description", "")
                variations = item_data.get("variations", [])
                
                if not item_name:
                    continue
                
                # Find first variation with fixed pricing
                price = 0.0
                price_cents = 0
                currency = "USD"
                variation_id = None
                has_fixed_price = False
                
                if variations:
                    for variation in variations:
                        if variation.get("type") == "ITEM_VARIATION" and not variation.get("is_deleted", False):
                            variation_data = variation.get("item_variation_data", {})
                            pricing_type = variation_data.get("pricing_type", "")
                            
                            # Use first variation with FIXED_PRICING
                            if pricing_type == "FIXED_PRICING":
                                price_money = variation_data.get("price_money", {})
                                if price_money:
                                    price_cents = price_money.get("amount", 0)
                                    price = float(price_cents) / 100.0 if price_cents else 0.0
                                    currency = price_money.get("currency", "USD")
                                    variation_id = variation.get("id")
                                    has_fixed_price = True
                                    break
                            elif not variation_id:
                                # Store first variation_id as fallback (even if variable pricing)
                                variation_id = variation.get("id")
                else:
                    # Item has no variations, check if it has a price
                    price_money = item_data.get("price_money", {})
                    if price_money:
                        price_cents = price_money.get("amount", 0)
                        price = float(price_cents) / 100.0 if price_cents else 0.0
                        currency = price_money.get("currency", "USD")
                        variation_id = item_id
                        has_fixed_price = True
                
                # Only include items with fixed pricing (skip variable pricing only items)
                if has_fixed_price or price > 0:
                    items.append(
                        {
                            "item_id": item_id,
                            "variation_id": variation_id or item_id,
                            "item_name": item_name,  # Use only base item name, no variation names
                            "description": item_description,
                            "price": price,
                            "price_cents": price_cents,
                            "currency": currency,
                            "sellable": True,
                        }
                    )
                else:
                    logger.debug(
                        f"[Square Menu Sync] Skipping item '{item_name}' (id={item_id}): "
                        f"no fixed price found (only variable pricing variations)"
                    )
        
        return items

    def sync_square_menu_to_db(
        self, restaurant_id: int, access_token: str, category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sync Square catalog menu items to our menu table.
        
        Args:
            restaurant_id: ID of the restaurant
            access_token: Square API access token
            category: Optional category to assign to all items (default: None)
        
        Returns:
            Dictionary with sync results
        """
        logger.info(f"[Square Menu Sync] Starting menu sync for restaurant {restaurant_id}")
        
        try:
            # Fetch Square catalog
            square_client = SquareClient(access_token)
            logger.info(f"[Square Menu Sync] Fetching Square catalog for restaurant {restaurant_id}")
            catalog_response = square_client.list_catalog(types=["ITEM"])
            square_items = self._flatten_square_catalog_items(catalog_response)
            
            logger.info(
                f"[Square Menu Sync] Found {len(square_items)} Square catalog item variations "
                f"for restaurant {restaurant_id}"
            )
            
            items_created = 0
            items_skipped = 0
            errors = []
            
            for square_item in square_items:
                item_name = square_item.get("item_name", "").strip()  # Use base item_name, not display name
                if not item_name:
                    logger.warning(f"[Square Menu Sync] Skipping item with empty name: {square_item}")
                    items_skipped += 1
                    continue
                
                # Check if item already exists (by base item name)
                existing_item = self.menu_repo.get_item_by_name(restaurant_id, item_name)
                if existing_item:
                    logger.debug(
                        f"[Square Menu Sync] Item '{item_name}' already exists (id={existing_item['id']}), skipping"
                    )
                    items_skipped += 1
                    continue
                
                # Get price - skip if price is 0 (variable pricing items)
                price = square_item.get("price", 0.0)
                if price <= 0:
                    logger.debug(
                        f"[Square Menu Sync] Skipping item '{item_name}': no fixed price (price={price})"
                    )
                    items_skipped += 1
                    continue
                
                # Create menu item
                try:
                    menu_data = {
                        "item_name": item_name,  # Use only base item name, no variation names
                        "item_desc": square_item.get("description", ""),
                        "price": price,
                        "category": category,
                        "sub_category": None,
                        "is_available": square_item.get("sellable", True),
                        "is_special": False,
                        "avg_prep_time": None,
                        "suggested_items": [],
                    }
                    
                    menu_id = self.menu_repo.create_menu(restaurant_id, menu_data)
                    items_created += 1
                    logger.info(
                        f"[Square Menu Sync] Created menu item: id={menu_id}, name='{item_name}', "
                        f"price={price} {square_item.get('currency', 'USD')}"
                    )
                except Exception as e:
                    error_msg = f"Error creating menu item '{item_name}': {str(e)}"
                    logger.error(f"[Square Menu Sync] {error_msg}")
                    errors.append(error_msg)
            
            logger.info(
                f"[Square Menu Sync] Completed menu sync for restaurant {restaurant_id}: "
                f"created={items_created}, skipped={items_skipped}, errors={len(errors)}"
            )
            
            return {
                "restaurant_id": restaurant_id,
                "success": True,
                "items_created": items_created,
                "items_skipped": items_skipped,
                "total_square_items": len(square_items),
                "errors": errors,
            }
        except Exception as e:
            logger.exception(f"[Square Menu Sync] Error syncing menu for restaurant {restaurant_id}: {e}")
            return {
                "restaurant_id": restaurant_id,
                "success": False,
                "error": str(e),
                "items_created": 0,
                "items_skipped": 0,
                "total_square_items": 0,
                "errors": [],
            }
