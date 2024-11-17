from datetime import datetime, timedelta
import uuid
from src.core.enums import OrderStage

class OrderProcessor:
    def __init__(self):
        pass

    def process_order(self, order):
        # Example logic to process an order
        if order.status == 'pending':
            # Update order status to preparing
            order.update_status('preparing')
            # Log the processing
            print(f"Order {order.id} is now being prepared.")
            # Simulate some processing time
            order.estimated_ready = datetime.now() + timedelta(minutes=15)
            return True
        return False