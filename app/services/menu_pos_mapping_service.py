from typing import Any, Dict, List, Optional

from app.integrations.square_client import SquareClient
from app.integrations.toast_client import ToastClient
from app.repositories.mysql_menu_pos_mapping_repo import MySQLMenuPOSMappingRepository
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class MenuPOSMappingService:
    def __init__(self):
        self.mapping_repo = MySQLMenuPOSMappingRepository()
        self.menu_repo = MySQLMenuRepository()

    def _flatten_toast_menu_items(self, menu_response: Dict) -> List[Dict]:
        items = []
        for menu in menu_response.get("menus", []):
            for group in menu.get("menuGroups", []):
                for item in group.get("menuItems", []):
                    items.append(
                        {
                            "guid": item.get("guid"),
                            "multiLocationId": item.get("multiLocationId"),
                            "name": item.get("name", ""),
                            "price": item.get("price", 0),
                            "description": item.get("description"),
                            "menuGroupName": group.get("name"),
                            "menuName": menu.get("name"),
                        }
                    )
        return items

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def find_matching_toast_item(self, our_menu_item: Dict, toast_menu_items: List[Dict]) -> Optional[Dict]:
        our_name = our_menu_item.get("item_name", "").lower().strip()
        our_price = float(our_menu_item.get("price", 0))

        exact_match = None
        fuzzy_matches = []
        price_matches = []

        for toast_item in toast_menu_items:
            toast_name = toast_item.get("name", "").lower().strip()
            toast_price = float(toast_item.get("price", 0))

            if our_name == toast_name:
                exact_match = toast_item
                break

            distance = self._levenshtein_distance(our_name, toast_name)
            if distance < 3:
                fuzzy_matches.append((toast_item, distance))

            if abs(our_price - toast_price) < 0.01 and our_price > 0:
                price_matches.append(toast_item)

        if exact_match:
            return exact_match

        if fuzzy_matches:
            fuzzy_matches.sort(key=lambda x: x[1])
            matched_item = fuzzy_matches[0][0]
            if matched_item in price_matches:
                return matched_item
            return matched_item

        if price_matches:
            return price_matches[0]

        return None

    def sync_menu_to_toast(
        self, restaurant_id: int, pos_integration_id: int, access_token: str, location_id: str
    ) -> Dict[str, Any]:
        toast_client = ToastClient(access_token)
        menu_response = toast_client.get_menus(location_id)
        toast_items = self._flatten_toast_menu_items(menu_response)

        our_menu_items = self.menu_repo.get_available_items_by_restaurant(restaurant_id)

        mappings_created = 0
        mappings_updated = 0
        unmatched_items = []

        for our_item in our_menu_items:
            matched_toast_item = self.find_matching_toast_item(our_item, toast_items)
            if matched_toast_item:
                guid = matched_toast_item.get("guid")
                if guid:
                    existing = self.mapping_repo.get_mapping(our_item["id"], pos_integration_id)
                    if existing:
                        self.mapping_repo.update_mapping(existing["id"], guid, matched_toast_item.get("name"))
                        mappings_updated += 1
                    else:
                        self.mapping_repo.create_mapping(
                            restaurant_id,
                            our_item["id"],
                            pos_integration_id,
                            guid,
                            matched_toast_item.get("name"),
                        )
                        mappings_created += 1
            else:
                unmatched_items.append(our_item)

        return {
            "mappings_created": mappings_created,
            "mappings_updated": mappings_updated,
            "unmatched_items": unmatched_items,
            "total_toast_items": len(toast_items),
            "total_our_items": len(our_menu_items),
        }

    def get_pos_menu_item_id(self, menu_item_id: int, pos_integration_id: int) -> Optional[str]:
        mapping = self.mapping_repo.get_mapping(menu_item_id, pos_integration_id)
        return mapping.get("pos_menu_item_id") if mapping else None

    def create_or_update_mapping(
        self,
        restaurant_id: int,
        menu_item_id: int,
        pos_integration_id: int,
        pos_menu_item_id: str,
        pos_menu_item_name: Optional[str] = None,
    ) -> int:
        return self.mapping_repo.create_mapping(
            restaurant_id, menu_item_id, pos_integration_id, pos_menu_item_id, pos_menu_item_name
        )

    def _flatten_square_catalog_items(self, catalog_response: Dict) -> List[Dict]:
        """
        Flatten Square catalog response to extract items with their variations.
        Returns a list where each entry represents an item variation (the actual sellable unit).
        """
        items = []
        catalog_objects = catalog_response.get("objects", [])
        
        for obj in catalog_objects:
            if obj.get("type") == "ITEM" and not obj.get("is_deleted", False):
                item_data = obj.get("item_data", {})
                item_id = obj.get("id")
                item_name = item_data.get("name", "")
                variations = item_data.get("variations", [])
                
                # If item has variations, create entries for each variation
                if variations:
                    for variation in variations:
                        if variation.get("type") == "ITEM_VARIATION" and not variation.get("is_deleted", False):
                            variation_data = variation.get("item_variation_data", {})
                            variation_id = variation.get("id")
                            variation_name = variation_data.get("name", "")
                            price_money = variation_data.get("price_money", {})
                            
                            # Use variation name if available, otherwise item name
                            display_name = variation_name if variation_name else item_name
                            # If both exist, combine them
                            if variation_name and item_name and variation_name != item_name:
                                display_name = f"{item_name} - {variation_name}"
                            
                            items.append(
                                {
                                    "item_id": item_id,
                                    "variation_id": variation_id,  # This is what we use as catalog_object_id
                                    "name": display_name,
                                    "item_name": item_name,
                                    "variation_name": variation_name,
                                    "price_cents": price_money.get("amount", 0),
                                    "currency": price_money.get("currency", "USD"),
                                    "price": float(price_money.get("amount", 0)) / 100.0,  # Convert cents to dollars
                                    "sku": variation_data.get("sku"),
                                    "sellable": variation_data.get("sellable", True),
                                    "stockable": variation_data.get("stockable", True),
                                }
                            )
                else:
                    # Item has no variations, use item itself (though Square typically requires variations)
                    items.append(
                        {
                            "item_id": item_id,
                            "variation_id": item_id,  # Fallback to item_id if no variations
                            "name": item_name,
                            "item_name": item_name,
                            "variation_name": "",
                            "price_cents": 0,
                            "currency": "USD",
                            "price": 0.0,
                            "sku": None,
                            "sellable": True,
                            "stockable": True,
                        }
                    )
        
        return items

    def find_matching_square_item(self, our_menu_item: Dict, square_items: List[Dict]) -> Optional[Dict]:
        """
        Find matching Square catalog item variation for our menu item.
        Uses name matching with fuzzy matching fallback.
        """
        our_name = our_menu_item.get("item_name", "").lower().strip()
        our_price = float(our_menu_item.get("price", 0))

        exact_match = None
        fuzzy_matches = []
        price_matches = []

        for square_item in square_items:
            square_name = square_item.get("name", "").lower().strip()
            square_price = float(square_item.get("price", 0))

            # Exact name match
            if our_name == square_name:
                exact_match = square_item
                break

            # Fuzzy name match (Levenshtein distance < 3)
            distance = self._levenshtein_distance(our_name, square_name)
            if distance < 3:
                fuzzy_matches.append((square_item, distance))

            # Price match (within $0.01 and both prices > 0)
            if abs(our_price - square_price) < 0.01 and our_price > 0 and square_price > 0:
                price_matches.append(square_item)

        if exact_match:
            return exact_match

        # Prefer fuzzy match that also matches price
        if fuzzy_matches:
            fuzzy_matches.sort(key=lambda x: x[1])  # Sort by distance
            matched_item = fuzzy_matches[0][0]
            if matched_item in price_matches:
                return matched_item
            return matched_item

        # Fallback to price match only
        if price_matches:
            return price_matches[0]

        return None

    def sync_menu_to_square(
        self, restaurant_id: int, pos_integration_id: int, access_token: str
    ) -> Dict[str, Any]:
        """
        Sync our menu items to Square catalog items.
        Fetches Square catalog and creates/updates mappings in Menu_POS_Mapping.
        Uses item variation IDs as pos_menu_item_id (catalog_object_id for orders).
        """
        square_client = SquareClient(access_token)
        
        # Fetch Square catalog (only ITEM type, variations are nested within items)
        logger.info(f"[Square Catalog Sync] Fetching Square catalog for restaurant {restaurant_id}")
        catalog_response = square_client.list_catalog(types=["ITEM"])
        square_items = self._flatten_square_catalog_items(catalog_response)
        
        logger.info(
            f"[Square Catalog Sync] Found {len(square_items)} Square catalog item variations for restaurant {restaurant_id}"
        )

        # Get our menu items
        our_menu_items = self.menu_repo.get_available_items_by_restaurant(restaurant_id)
        logger.info(
            f"[Square Catalog Sync] Found {len(our_menu_items)} menu items in our database for restaurant {restaurant_id}"
        )

        mappings_created = 0
        mappings_updated = 0
        unmatched_items = []

        for our_item in our_menu_items:
            matched_square_item = self.find_matching_square_item(our_item, square_items)
            if matched_square_item:
                # Use variation_id as pos_menu_item_id (this is the catalog_object_id for orders)
                variation_id = matched_square_item.get("variation_id")
                item_name = matched_square_item.get("name", "")
                
                if variation_id:
                    existing = self.mapping_repo.get_mapping(our_item["id"], pos_integration_id)
                    if existing:
                        self.mapping_repo.update_mapping(existing["id"], variation_id, item_name)
                        mappings_updated += 1
                        logger.debug(
                            f"[Square Catalog Sync] Updated mapping: menu_item_id={our_item['id']} -> "
                            f"square_variation_id={variation_id} ({item_name})"
                        )
                    else:
                        self.mapping_repo.create_mapping(
                            restaurant_id,
                            our_item["id"],
                            pos_integration_id,
                            variation_id,
                            item_name,
                        )
                        mappings_created += 1
                        logger.debug(
                            f"[Square Catalog Sync] Created mapping: menu_item_id={our_item['id']} -> "
                            f"square_variation_id={variation_id} ({item_name})"
                        )
                else:
                    logger.warning(
                        f"[Square Catalog Sync] Matched Square item has no variation_id: {matched_square_item}"
                    )
                    unmatched_items.append(our_item)
            else:
                unmatched_items.append(our_item)
                logger.debug(
                    f"[Square Catalog Sync] No match found for menu item: {our_item.get('item_name')} "
                    f"(id={our_item.get('id')})"
                )

        return {
            "mappings_created": mappings_created,
            "mappings_updated": mappings_updated,
            "unmatched_items": unmatched_items,
            "total_square_items": len(square_items),
            "total_our_items": len(our_menu_items),
        }
