from datetime import datetime
from src.core.enums import OrderStage

class OrderContext:
    def __init__(self):
        self.current_drink = None
        self.modifications = []
        self.stage = OrderStage.MENU
        self.last_interaction = datetime.now()
        self.pending_item = None
        self.pending_modifier = None

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