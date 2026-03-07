"""
Background service for syncing Square catalog to menu_pos_mapping table.
Uses fuzzy matching (>=85% similarity) to match catalog items with menu items.
"""

from typing import Any, Dict, List, Optional

from app.config import settings
from app.integrations.square_client import SquareClient
from app.repositories.mysql_menu_pos_mapping_repo import MySQLMenuPOSMappingRepository
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_pos_integration_repo import MySQLPOSIntegrationRepository
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class SquareCatalogSyncService:
    """Service for syncing Square catalog items to menu_pos_mapping using fuzzy matching."""

    def __init__(self):
        self.menu_repo = MySQLMenuRepository()
        self.mapping_repo = MySQLMenuPOSMappingRepository()
        self.pos_integration_repo = MySQLPOSIntegrationRepository()
        self.restaurant_repo = MySQLRestaurantRepository()

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
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

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """
        Calculate similarity percentage between two strings.
        Returns a value between 0 and 100.
        """
        if not s1 and not s2:
            return 100.0
        if not s1 or not s2:
            return 0.0
        
        # Normalize strings: lowercase, strip whitespace
        s1_normalized = s1.lower().strip()
        s2_normalized = s2.lower().strip()
        
        # Exact match
        if s1_normalized == s2_normalized:
            return 100.0
        
        # Calculate Levenshtein distance
        distance = self._levenshtein_distance(s1_normalized, s2_normalized)
        max_len = max(len(s1_normalized), len(s2_normalized))
        
        # Calculate similarity percentage
        if max_len == 0:
            return 100.0
        
        similarity = (1.0 - (distance / max_len)) * 100.0
        return similarity

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

    def find_matching_square_item(
        self, our_menu_item: Dict, square_items: List[Dict], threshold: float = 85.0
    ) -> Optional[Dict]:
        """
        Find matching Square catalog item variation for our menu item using fuzzy matching.
        Only returns matches with similarity >= threshold (default 85%).
        
        Args:
            our_menu_item: Our menu item from database
            square_items: List of flattened Square catalog items
            threshold: Minimum similarity percentage (0-100)
        
        Returns:
            Matching Square item if found, None otherwise
        """
        our_name = our_menu_item.get("item_name", "").strip()
        if not our_name:
            return None

        best_match = None
        best_similarity = 0.0

        for square_item in square_items:
            square_name = square_item.get("name", "").strip()
            if not square_name:
                continue
            
            similarity = self._calculate_similarity(our_name, square_name)
            
            if similarity >= threshold and similarity > best_similarity:
                best_match = square_item
                best_similarity = similarity

        if best_match:
            logger.debug(
                f"Matched '{our_name}' with '{best_match.get('name')}' "
                f"(similarity: {best_similarity:.2f}%)"
            )
            return best_match

        return None

    def sync_restaurant_catalog(self, restaurant_id: int) -> Dict[str, Any]:
        """
        Sync Square catalog to menu_pos_mapping for a specific restaurant.
        
        Args:
            restaurant_id: ID of the restaurant
        
        Returns:
            Dictionary with sync results
        """
        logger.info(f"[Square Catalog Sync] Starting sync for restaurant {restaurant_id}")
        
        # Get Square POS integration for this restaurant
        pos_integrations = self.pos_integration_repo.get_enabled_integrations(restaurant_id)
        square_integration = None
        for integration in pos_integrations:
            if integration.get("pos_type") == "SQUARE":
                square_integration = integration
                break
        
        if not square_integration:
            logger.info(f"[Square Catalog Sync] No Square integration found for restaurant {restaurant_id}")
            return {
                "restaurant_id": restaurant_id,
                "success": False,
                "error": "No Square POS integration found",
                "mappings_created": 0,
                "mappings_updated": 0,
                "unmatched_items": [],
            }
        
        # Get Square access token from credentials
        credentials = square_integration.get("credentials", {})
        if isinstance(credentials, str):
            import json
            try:
                credentials = json.loads(credentials)
            except json.JSONDecodeError:
                logger.error(f"[Square Catalog Sync] Invalid credentials JSON for restaurant {restaurant_id}")
                return {
                    "restaurant_id": restaurant_id,
                    "success": False,
                    "error": "Invalid credentials format",
                    "mappings_created": 0,
                    "mappings_updated": 0,
                    "unmatched_items": [],
                }
        
        access_token = credentials.get("access_token")
        if not access_token:
            logger.error(f"[Square Catalog Sync] No access_token in credentials for restaurant {restaurant_id}")
            return {
                "restaurant_id": restaurant_id,
                "success": False,
                "error": "No access_token in credentials",
                "mappings_created": 0,
                "mappings_updated": 0,
                "unmatched_items": [],
            }
        
        pos_integration_id = square_integration.get("id")
        
        try:
            # Fetch Square catalog
            square_client = SquareClient(access_token)
            logger.info(f"[Square Catalog Sync] Fetching Square catalog for restaurant {restaurant_id}")
            catalog_response = square_client.list_catalog(types=["ITEM"])
            square_items = self._flatten_square_catalog_items(catalog_response)
            
            logger.info(
                f"[Square Catalog Sync] Found {len(square_items)} Square catalog item variations "
                f"for restaurant {restaurant_id}"
            )
            
            # Log Square catalog items found
            if square_items:
                logger.info(f"[Square Catalog Sync] Square catalog items for restaurant {restaurant_id}:")
                for idx, sq_item in enumerate(square_items[:20], 1):  # Log first 20 items
                    logger.info(
                        f"  [{idx}] Square Item: base_name='{sq_item.get('item_name')}', "
                        f"display_name='{sq_item.get('name')}', "
                        f"variation_id={sq_item.get('variation_id')}, "
                        f"price={sq_item.get('price', 0):.2f} {sq_item.get('currency', 'USD')}"
                    )
                if len(square_items) > 20:
                    logger.info(f"  ... and {len(square_items) - 20} more Square items")
            else:
                logger.warning(f"[Square Catalog Sync] No Square catalog items found for restaurant {restaurant_id}")
            
            # Get our menu items
            our_menu_items = self.menu_repo.get_available_items_by_restaurant(restaurant_id)
            logger.info(
                f"[Square Catalog Sync] Found {len(our_menu_items)} menu items in our database "
                f"for restaurant {restaurant_id}"
            )
            
            # Log our menu items found
            if our_menu_items:
                logger.info(f"[Square Catalog Sync] Our menu items for restaurant {restaurant_id}:")
                for idx, our_item in enumerate(our_menu_items[:20], 1):  # Log first 20 items
                    logger.info(
                        f"  [{idx}] Our Item: '{our_item.get('item_name')}' "
                        f"(id={our_item.get('id')}, price={our_item.get('price', 0):.2f})"
                    )
                if len(our_menu_items) > 20:
                    logger.info(f"  ... and {len(our_menu_items) - 20} more menu items")
            else:
                logger.warning(f"[Square Catalog Sync] No menu items found in our database for restaurant {restaurant_id}")
            
            threshold = settings.SQUARE_CATALOG_FUZZY_MATCH_THRESHOLD
            mappings_created = 0
            mappings_updated = 0
            unmatched_items = []
            
            logger.info(
                f"[Square Catalog Sync] Starting matching process for restaurant {restaurant_id} "
                f"with threshold: {threshold}%"
            )
            
            for our_item in our_menu_items:
                our_item_name = our_item.get("item_name", "").strip()
                our_item_id = our_item.get("id")
                our_item_price = our_item.get("price", 0)
                
                if not our_item_name:
                    logger.warning(
                        f"[Square Catalog Sync] Skipping menu item id={our_item_id}: empty item_name"
                    )
                    unmatched_items.append(our_item)
                    continue
                
                # Find best match with detailed logging
                # Only match against base item_name, not variation names
                best_match = None
                best_similarity = 0.0
                all_similarities = []
                
                logger.debug(
                    f"[Square Catalog Sync] Searching for match for '{our_item_name}' (id={our_item_id}) "
                    f"in {len(square_items)} Square items"
                )
                
                for square_item in square_items:
                    # Only match against base item name
                    square_base_name = square_item.get("item_name", "").strip()
                    
                    if not square_base_name:
                        continue
                    
                    # Calculate similarity against base name only
                    similarity = self._calculate_similarity(our_item_name, square_base_name)
                    all_similarities.append((square_item, similarity, "base_item_name", square_base_name))
                    
                    # For exact matches (100%), prefer the first variation found
                    # For fuzzy matches, prefer higher similarity
                    if similarity >= threshold:
                        if similarity == 100.0 and best_similarity < 100.0:
                            # Exact match found - use this one
                            best_match = square_item
                            best_similarity = similarity
                            logger.debug(
                                f"[Square Catalog Sync] Found exact match: '{our_item_name}' = '{square_base_name}' "
                                f"(variation_id={square_item.get('variation_id')})"
                            )
                        elif similarity > best_similarity:
                            # Better fuzzy match
                            best_match = square_item
                            best_similarity = similarity
                        elif similarity == best_similarity == 100.0 and best_match is None:
                            # First exact match
                            best_match = square_item
                            best_similarity = similarity
                            logger.debug(
                                f"[Square Catalog Sync] Found first exact match: '{our_item_name}' = '{square_base_name}' "
                                f"(variation_id={square_item.get('variation_id')})"
                            )
                
                # Log all similarity scores for this item (top 5) - only for item id 79
                if our_item_id == 79 and all_similarities:
                    all_similarities.sort(key=lambda x: x[1], reverse=True)
                    top_matches = all_similarities[:5]
                    logger.info(
                        f"[Square Catalog Sync] Matching '{our_item_name}' (id={our_item_id}, price={our_item_price:.2f}):"
                    )
                    for sq_item, sim, match_type, matched_name in top_matches:
                        display_name = sq_item.get("name", "")
                        logger.info(
                            f"  - '{matched_name}' ({match_type}) -> '{display_name}' "
                            f"(variation_id={sq_item.get('variation_id')}): {sim:.2f}% similarity"
                        )
                
                if best_match:
                    variation_id = best_match.get("variation_id")
                    matched_name = best_match.get("name", "")
                    matched_price = best_match.get("price", 0)
                    
                    # Only log detailed match info for item id 79
                    if our_item_id == 79:
                        logger.info(
                            f"[Square Catalog Sync] ✓ MATCHED: '{our_item_name}' (id={our_item_id}) -> "
                            f"'{matched_name}' (variation_id={variation_id}) with {best_similarity:.2f}% similarity"
                        )
                    
                    if not variation_id:
                        if our_item_id == 79:
                            logger.warning(
                                f"[Square Catalog Sync] ✗ SKIPPED: Matched Square item has no variation_id. "
                                f"Our item: '{our_item_name}' (id={our_item_id}), Square item: '{matched_name}'"
                            )
                        unmatched_items.append(our_item)
                        continue
                    
                    existing = self.mapping_repo.get_mapping(our_item_id, pos_integration_id)
                    if existing:
                        old_variation_id = existing.get("pos_menu_item_id")
                        old_name = existing.get("pos_menu_item_name", "")
                        
                        if old_variation_id == variation_id:
                            if our_item_id == 79:
                                logger.info(
                                    f"[Square Catalog Sync] → NO UPDATE: Mapping already exists and matches. "
                                    f"menu_item_id={our_item_id} -> square_variation_id={variation_id}"
                                )
                        else:
                            self.mapping_repo.update_mapping(existing["id"], variation_id, matched_name)
                            mappings_updated += 1
                            if our_item_id == 79:
                                logger.info(
                                    f"[Square Catalog Sync] → UPDATED: Mapping updated. "
                                    f"menu_item_id={our_item_id}: "
                                    f"'{old_name}' (variation_id={old_variation_id}) -> "
                                    f"'{matched_name}' (variation_id={variation_id})"
                                )
                    else:
                        self.mapping_repo.create_mapping(
                            restaurant_id,
                            our_item_id,
                            pos_integration_id,
                            variation_id,
                            matched_name,
                        )
                        mappings_created += 1
                        if our_item_id == 79:
                            logger.info(
                                f"[Square Catalog Sync] → CREATED: New mapping created. "
                                f"menu_item_id={our_item_id} -> square_variation_id={variation_id} "
                                f"('{our_item_name}' -> '{matched_name}')"
                            )
                else:
                    # No match found - log why (only for item id 79)
                    if our_item_id == 79:
                        max_similarity = max([sim for _, sim, _, _ in all_similarities]) if all_similarities else 0.0
                        if max_similarity > 0:
                            logger.warning(
                                f"[Square Catalog Sync] ✗ NO MATCH: '{our_item_name}' (id={our_item_id}). "
                                f"Best similarity: {max_similarity:.2f}% (below threshold of {threshold}%)"
                            )
                        else:
                            logger.warning(
                                f"[Square Catalog Sync] ✗ NO MATCH: '{our_item_name}' (id={our_item_id}). "
                                f"No similar items found in Square catalog."
                            )
                    unmatched_items.append(our_item)
            
            logger.info(
                f"[Square Catalog Sync] Completed sync for restaurant {restaurant_id}: "
                f"created={mappings_created}, updated={mappings_updated}, unmatched={len(unmatched_items)}"
            )
            
            return {
                "restaurant_id": restaurant_id,
                "success": True,
                "mappings_created": mappings_created,
                "mappings_updated": mappings_updated,
                "unmatched_items": [{"id": item["id"], "item_name": item["item_name"]} for item in unmatched_items],
                "total_square_items": len(square_items),
                "total_our_items": len(our_menu_items),
            }
        except Exception as e:
            logger.exception(f"[Square Catalog Sync] Error syncing restaurant {restaurant_id}: {e}")
            return {
                "restaurant_id": restaurant_id,
                "success": False,
                "error": str(e),
                "mappings_created": 0,
                "mappings_updated": 0,
                "unmatched_items": [],
            }

    def sync_all_restaurants(self) -> Dict[str, Any]:
        """
        Sync Square catalog to menu_pos_mapping for all restaurants with Square integration.
        
        Returns:
            Dictionary with overall sync results
        """
        logger.info("[Square Catalog Sync] Starting sync for all restaurants")
        
        # Get all restaurants
        restaurants = self.restaurant_repo.get_all_restaurants()
        logger.info(f"[Square Catalog Sync] Found {len(restaurants)} restaurants")
        
        results = []
        total_created = 0
        total_updated = 0
        total_failed = 0
        
        for restaurant in restaurants:
            restaurant_id = restaurant.get("id")
            result = self.sync_restaurant_catalog(restaurant_id)
            results.append(result)
            
            if result.get("success"):
                total_created += result.get("mappings_created", 0)
                total_updated += result.get("mappings_updated", 0)
            else:
                total_failed += 1
        
        logger.info(
            f"[Square Catalog Sync] Completed sync for all restaurants: "
            f"created={total_created}, updated={total_updated}, failed={total_failed}"
        )
        
        return {
            "success": True,
            "total_restaurants": len(restaurants),
            "total_mappings_created": total_created,
            "total_mappings_updated": total_updated,
            "total_failed": total_failed,
            "results": results,
        }
