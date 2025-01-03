"""Menu handling utilities"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class MenuHandler:
    def __init__(self, menu: Dict[int, Dict[str, Any]], modifiers: Dict[str, Dict[str, float]]):
        self.menu = menu
        self.modifiers = modifiers
        
    def get_menu_item(self, item_name: str, is_iced: bool = False) -> Dict[str, Any]:
        """Get menu item with special handling for iced drinks"""
        item_name = item_name.lower()
        
        # Handle iced variations
        if is_iced and 'latte' in item_name:
            for item in self.menu.values():
                if 'iced latte' in item['item'].lower():
                    return item.copy()
        
        # Handle regular items
        for item in self.menu.values():
            if item['item'].lower() == item_name:
                return item.copy()
        
        return None
    
    def parse_modifiers(self, message: str) -> List[str]:
        """Parse modifiers from message"""
        message = message.lower()
        found_modifiers = []
        
        # Define modifier variations
        modifier_variations = {
            'almond milk': ['almond milk', 'almond'],
            'oat milk': ['oat milk', 'oat', 'oatly'],
            'soy milk': ['soy milk', 'soy']
        }
        
        for mod_name, variations in modifier_variations.items():
            if any(var in message for var in variations):
                found_modifiers.append(mod_name)
        
        return found_modifiers
    
    def extract_menu_items_and_modifiers(self, message: str) -> List[Dict[str, Any]]:
        """Extract all menu items and their modifiers from a message"""
        found_items = []
        message = message.lower()
        
        # Check for iced/cold specification
        is_iced = 'iced' in message or 'cold' in message
        
        # Find menu items
        for item in self.menu.values():
            item_name = item['item'].lower()
            
            # Special handling for lattes
            if 'latte' in item_name:
                if is_iced and not 'iced' in item_name:
                    continue  # Skip regular latte if iced was specified
                if not is_iced and 'iced' in item_name:
                    continue  # Skip iced latte if iced wasn't specified
            
            if item_name in message:
                item_copy = item.copy()
                item_copy['modifiers'] = self.parse_modifiers(message)
                found_items.append(item_copy)
        
        return found_items
    
    def format_item_for_display(self, item: Dict[str, Any], with_modifications: bool = True) -> str:
        """Format menu item for display"""
        base = f"{item['item']} (${item['price']:.2f})"
        if with_modifications and item.get('modifiers'):
            mods = ', '.join(item['modifiers'])
            return f"{base} with {mods}"
        return base