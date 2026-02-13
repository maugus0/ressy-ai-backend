from typing import Any, Dict, List, Optional

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
