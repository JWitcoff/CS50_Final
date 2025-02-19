from datetime import datetime, timedelta
import uuid
from src.core.enums import OrderStage

class OrderQueue:
    def __init__(self):
        self.items = []
        self.current_index = 0

    def add_items(self, items):
        """Add multiple items to be processed"""
        self.items.extend(items)

    def get_next(self):
        """Get next item to process"""
        if self.current_index < len(self.items):
            item = self.items[self.current_index]
            self.current_index += 1
            return item
        return None

    def has_more(self):
        """Check if more items need processing"""
        return self.current_index < len(self.items)

class OrderProcessor:
    def __init__(self):
        pass

    def process_next_item(self, phone_number, active_orders):
        """Process next item in the queue"""
        order = active_orders[phone_number]
        queue = order['order_queue']
        
        if not queue.has_more():
            # Show cart summary when no more items
            return order['cart'].get_summary()
            
        next_item = queue.get_next()
        
        # Check if item needs modifier
        if next_item['category'] in ['hot', 'cold']:
            # Store original message context
            order['pending_item'] = next_item
            order['state'] = OrderStage.AWAITING_MOD_CONFIRM  # Fixed: Using OrderStage enum
            return (f"Would you like {next_item['item']} with any modifications?\n"
                   "Available options: almond milk, oat milk, soy milk (+$0.75 each)")
        else:
            # Add non-drink items directly to cart
            order['cart'].add_item(next_item)
            return self.process_next_item(phone_number, active_orders)

    def process_order(self, order):
        """Process a pending order"""
        if order.status == 'pending':
            order.update_status('preparing')
            order.estimated_ready = datetime.now() + timedelta(minutes=15)
            return True
        return False

    def handle_done(self, phone_number, active_orders):
        """Handle DONE command"""
        if phone_number not in active_orders:
            return "No active order found. Please start a new order."
        
        cart = active_orders[phone_number]['cart']
        if cart.is_empty():
            return "Your cart is empty! Please add items before checking out."
        
        # Show cart summary before payment
        summary = cart.get_summary()
        active_orders[phone_number]['state'] = OrderStage.PAYMENT
        
        return (
            f"{summary}\n\n"
            "Ready to complete your order! How would you like to pay?\n"
            "- Reply CASH for cash payment\n"
            "- Reply CARD for credit card"
        )

class Order:
    def __init__(self, phone_number, cart):
        self.id = str(uuid.uuid4())[:8]  # Short unique ID
        self.phone_number = phone_number
        self.items = cart.items.copy()
        self.total = cart.get_total()
        self.status = 'pending'
        self.created_at = datetime.now()
        self.estimated_ready = self.created_at + timedelta(minutes=15)
        self.payment_method = None

    def update_status(self, status):
        """Update order status"""
        self.status = status