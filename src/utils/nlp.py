import re
from src.core.enums import OrderStage 

def extract_drink_order(user_message, menu):
    """Extract drink order from user message."""
    # Example implementation
    for item_id, details in menu.items():
        if details['item'].lower() in user_message.lower():
            return details['item']
    return None

def extract_modifications(user_message):
    """Extract modifications from user message."""
    mods = []
    mod_patterns = {
        'milk': r'(oat|soy|almond) milk',
        'temp': r'(hot|iced)',
        'shots': r'(extra|double) shot'
    }
    
    for mod_type, pattern in mod_patterns.items():
        match = re.search(pattern, user_message.lower())
        if match:
            mods.append(match.group(0))
    return mods 