"""Menu handling utilities"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class MenuHandler:
    def __init__(self, menu: Dict[int, Dict[str, Any]], modifiers: Dict[str, Dict[str, float]]):
        self.menu = menu
        self.modifiers = modifiers

    def extract_menu_items_and_modifiers(self, message: str) -> List[Dict[str, Any]]:
        """Extract menu items and their modifiers from a message"""
        found_items = []
        message = message.lower()
        
        # First look for iced/cold drinks
        is_iced = 'iced' in message or 'cold' in message
        
        # Define modifier variations
        milk_modifiers = {
            'almond milk': ['almond milk', 'almond'],
            'oat milk': ['oat milk', 'oat'],
            'soy milk': ['soy milk', 'soy']
        }
        
        for menu_id, item in self.menu.items():
            item_name = item['item'].lower()
            
            # Handle iced drinks specially
            if is_iced and 'latte' in item_name:
                if not 'iced' in item_name:
                    continue  # Skip regular lattes if iced was specified
            elif not is_iced and 'iced' in item_name:
                continue  # Skip iced drinks if iced wasn't specified
            
            if item_name in message:
                # Create a copy of the item
                item_copy = item.copy()
                item_copy['modifiers'] = []
                
                # Check for modifiers
                for mod_name, variations in milk_modifiers.items():
                    if any(var in message for var in variations):
                        item_copy['modifiers'].append(mod_name)
                
                # For lattes, if iced was specified, use the iced latte item
                if is_iced and 'latte' in item_name and not 'iced' in item_name:
                    for menu_item in self.menu.values():
                        if 'iced latte' in menu_item['item'].lower():
                            item_copy.update({k: v for k, v in menu_item.items() if k != 'modifiers'})
                            break
                
                found_items.append(item_copy)
        
        return found_items

    def get_item_description(self, item_name: str) -> str:
        """Get full description of a menu item"""
        for item in self.menu.values():
            if item['item'].lower() == item_name.lower():
                return f"{item['item']} (${item['price']:.2f}): {item['description']}"
        return "Item not found"

    def get_modifier_cost(self, modifier_name: str) -> float:
        """Get cost of a modifier"""
        for category in self.modifiers.values():
            if modifier_name in category:
                return category[modifier_name]
        return 0.0