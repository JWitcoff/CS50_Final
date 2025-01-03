"""Menu handling utilities"""
import logging
from typing import List, Dict, Any
from .enums import OrderStage

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
            'oat milk': ['oat milk', 'oat', 'oatly'],
            'soy milk': ['soy milk', 'soy']
        }
        
        # First check for menu numbers
        for menu_id, item in self.menu.items():
            # Check for menu number in message
            if str(menu_id) in message:
                item_copy = item.copy()
                item_copy['modifiers'] = []
                found_items.append(item_copy)
                continue
                
            item_name = item['item'].lower()
            
            # Handle iced drinks specifically
            if 'latte' in item_name:
                if is_iced:
                    if 'iced' not in item_name:
                        continue  # Skip regular latte if iced was specified
                elif 'iced' in item_name:
                    continue  # Skip iced latte if iced wasn't specified
            
            # Check if item name is in message
            if item_name in message:
                item_copy = item.copy()
                item_copy['modifiers'] = []
                
                # Process modifiers for drinks
                if item_copy['category'] in ['hot', 'cold']:
                    for mod_name, variations in milk_modifiers.items():
                        if any(var in message for var in variations):
                            item_copy['modifiers'].append(mod_name)
                
                # Handle iced latte special case
                if is_iced and 'latte' in item_name and 'iced' not in item_name:
                    # Find and use iced latte entry
                    for menu_item in self.menu.values():
                        if menu_item['item'].lower() == 'iced latte':
                            base_item = menu_item.copy()
                            base_item['modifiers'] = item_copy['modifiers']
                            item_copy = base_item
                            break
                
                found_items.append(item_copy)
        
        logger.info(f"Extracted items: {found_items}")
        return found_items
    
    def check_for_modification(self, message: str) -> tuple[bool, str]:
        """Check if message contains a modifier and return (has_modifier, modifier_name)"""
        message = message.lower()
        
        modifier_variations = {
            'almond milk': ['almond milk', 'almond'],
            'oat milk': ['oat milk', 'oat', 'oatly'],
            'soy milk': ['soy milk', 'soy']
        }
        
        for mod_name, variations in modifier_variations.items():
            if any(var in message for var in variations):
                return True, mod_name
                
        return False, ""
    
    def get_modifier_cost(self, modifier_name: str) -> float:
        """Get the cost of a modifier"""
        for category in self.modifiers.values():
            if modifier_name in category:
                return category[modifier_name]
        return 0.0
    
    def is_confirmation(self, message: str) -> bool:
        """Check if message is a confirmation"""
        confirmations = ['yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'y', 'alright', 'confirm']
        return message.lower().strip() in confirmations
    
    def is_denial(self, message: str) -> bool:
        """Check if message is a denial"""
        denials = ['no', 'nope', 'n', 'regular', 'normal', 'none', 'cancel']
        return message.lower().strip() in denials