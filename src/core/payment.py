import re
from src.core.state import OrderContext
from src.core.enums import OrderStage

class PaymentHandler:
    def __init__(self):
        pass

    def process_payment(self, order, payment_details):
        # Implement your payment processing logic here
        # For example, validate payment details and update order status
        if self.validate_payment(payment_details):
            order.update_status(OrderStage.CHECKOUT)
            return True
        return False

    def validate_payment(self, payment_details):
        # Implement payment validation logic
        # This is a placeholder for actual validation logic
        return payment_details == "4242-4242-4242"