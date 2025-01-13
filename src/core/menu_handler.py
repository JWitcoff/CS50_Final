"""Menu handling utilities"""
import logging
from typing import List, Dict, Any, Tuple
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
        words = message.split()
        
        # First look for iced/cold drinks
        is_iced = 'iced' in message or 'cold' in message
        
        # Define modifier variations
        milk_modifiers = {
            'almond milk': ['almond milk', 'almond'],
            'oat milk': ['oat milk', 'oat', 'oatly'],
            'soy milk': ['soy milk', 'soy']
        }
        
        # First check for numeric menu references
        for menu_id, menu_item in self.menu.items():
            if str(menu_id) in message:
                # Get the original menu item by ID and preserve its case
                original_item = self.menu[menu_id].copy()
                processed_item = self._process_item(original_item, is_iced, milk_modifiers, message)
                if processed_item:
                    found_items.append(processed_item)
        
        # Then check for item names if no numeric reference found
        if not found_items:
            for menu_id, item in self.menu.items():
                # Check item name - use original case for comparison
                original_name = item['item']
                if self._check_item_match(original_name.lower(), words, is_iced):
                    # Use original item name
                    item_copy = item.copy()
                    processed_item = self._process_item(item_copy, is_iced, milk_modifiers, message)
                    if processed_item:
                        found_items.append(processed_item)
        
        logger.info(f"Extracted items: {found_items}")
        return found_items
    
    def _check_item_match(self, item_name: str, words: List[str], is_iced: bool) -> bool:
        """Check if item matches message considering word order"""
        # Handle iced variations
        if 'latte' in item_name:
            if is_iced and 'iced' not in item_name:
                return False
            if not is_iced and 'iced' in item_name:
                return False
        
        # Remove 'with' from item name for matching
        item_words = set(item_name.replace('with', '').split())
        message_words = set(words)
        
        # Check if all item words appear in message
        return all(word in message_words for word in item_words)
    
    def _process_item(self, item: Dict, is_iced: bool, milk_modifiers: Dict, message: str) -> Dict:
        """Process item and extract modifiers"""
        item_copy = item.copy()
        item_copy['modifiers'] = []
        
        # Handle iced latte special case while preserving original case
        if is_iced and 'latte' in item['item'].lower() and 'iced' not in item['item'].lower():
            for menu_item in self.menu.values():
                if menu_item['item'].lower() == 'iced latte':
                    temp = menu_item.copy()
                    temp['item'] = menu_item['item']  # Preserve original case
                    item_copy = temp
                    break
        
        # Check for modifiers
        if item_copy['category'] in ['hot', 'cold']:
            for mod_name, variations in milk_modifiers.items():
                if any(var in message for var in variations):
                    item_copy['modifiers'].append(mod_name)
        
        return item_copy
    
    def check_for_modification(self, message: str) -> Tuple[bool, str]:
        """Check if message contains a modifier"""
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
    
    def is_confirmation(self, message: str) -> bool:
        """Check if message is a confirmation"""
        confirmations = ['yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'y', 
                        'alright', 'confirm', 'yup', 'ya', 'ye']
        message = message.lower().strip('!., ')
        return message in confirmations or message.startswith('y')
    
    def is_denial(self, message: str) -> bool:
        """Check if message is a denial"""
        denials = ['no', 'nope', 'n', 'regular', 'normal', 'none', 'cancel', 'nah']
        message = message.lower().strip('!., ')
        return message in denials