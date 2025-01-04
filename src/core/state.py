from datetime import datetime
from typing import List, Dict, Optional
from src.core.enums import OrderStage

class CustomerContext:
    """Tracks customer history and preferences"""
    def __init__(self):
        self.favorite_items = []
        self.usual_modifications = []
        self.visit_count = 0
        self.last_visit = None
        self.last_order = None
        self.preferred_payment = None
        self.conversation_history = []

    def update_from_order(self, order_details: Dict):
        """Update context based on new order"""
        self.visit_count += 1
        self.last_visit = datetime.now()
        self.last_order = order_details
        
        # Update favorites (keep last 3)
        if 'items' in order_details:
            for item in order_details['items']:
                if item not in self.favorite_items:
                    self.favorite_items.append(item)
            self.favorite_items = self.favorite_items[-3:]
            
        # Update usual modifications
        if 'modifications' in order_details:
            for mod in order_details['modifications']:
                if mod not in self.usual_modifications:
                    self.usual_modifications.append(mod)
                    
    def add_conversation_entry(self, message: str, response: str):
        """Add to conversation history (keep last 5)"""
        self.conversation_history.append({
            'timestamp': datetime.now(),
            'message': message,
            'response': response
        })
        self.conversation_history = self.conversation_history[-5:]

class OrderContext:
    """Tracks current order state and details"""
    def __init__(self):
        self.stage = OrderStage.MENU
        self.last_interaction = datetime.now()
        self.current_drink = None
        self.modifications = []
        self.pending_item = None
        self.pending_modifier = None
        self.suggested_items = []
        self.chat_context = {}
        self.last_error = None

    def update_stage(self, new_stage: OrderStage):
        """Update stage and last interaction time"""
        self.stage = new_stage
        self.last_interaction = datetime.now()

    def set_pending_item(self, item):
        """Set pending item for modification"""
        self.pending_item = item
        
    def set_pending_modifier(self, modifier):
        """Set pending modifier"""
        self.pending_modifier = modifier
        
    def clear_pending(self):
        """Clear pending items and modifiers"""
        self.pending_item = None
        self.pending_modifier = None
        
    def add_suggestion(self, item: str, reason: str):
        """Add suggested item with reason"""
        self.suggested_items.append({
            'item': item,
            'reason': reason,
            'timestamp': datetime.now()
        })
        
    def get_active_suggestions(self) -> List[Dict]:
        """Get suggestions not yet purchased"""
        current_time = datetime.now()
        return [
            sugg for sugg in self.suggested_items
            if (current_time - sugg['timestamp']).seconds < 300  # 5 minute timeout
        ]
        
    def set_error(self, error_type: str, details: str):
        """Track last error for better error handling"""
        self.last_error = {
            'type': error_type,
            'details': details,
            'timestamp': datetime.now()
        }
        
    def clear_error(self):
        """Clear error state"""
        self.last_error = None
        
    def update_chat_context(self, key: str, value: str):
        """Update conversation context"""
        self.chat_context[key] = {
            'value': value,
            'timestamp': datetime.now()
        }
        
    def get_chat_context(self, key: str) -> Optional[str]:
        """Get conversation context if still relevant"""
        if key in self.chat_context:
            context = self.chat_context[key]
            if (datetime.now() - context['timestamp']).seconds < 300:  # 5 minute timeout
                return context['value']
        return None