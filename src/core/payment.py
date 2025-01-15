import uuid
from datetime import datetime
from src.core.enums import OrderStage
from src.core.order import Order

class PaymentHandler:
    def __init__(self):
        self.payment_methods = {
            'credit': self._handle_credit_card,
            'card': self._handle_credit_card,
            'cash': self._handle_cash
        }

    def handle_payment(self, phone_number, message, active_orders, completed_orders):
        """Handle payment method selection"""
        message = message.lower()
        
        if phone_number not in active_orders:
            return "No active order found. Please start a new order."
            
        cart = active_orders[phone_number]['cart']
        
        if message == 'cash':
            # Create Order object
            new_order = Order(phone_number, cart)
            new_order.payment_method = 'cash'
            
            # Move to completed orders
            if phone_number not in completed_orders:
                completed_orders[phone_number] = []
            
            completed_orders[phone_number].append(new_order)
            
            # Clear from active orders
            del active_orders[phone_number]
            
            return (
                f"Great choice! 😊 Please pay ${new_order.total:.2f} when you pick up your order. "
                f"Your order number is #{new_order.id}. "
                f"It'll be ready at {new_order.estimated_ready.strftime('%I:%M %p')}. "
                f"Enjoy your treats!"
            )
        
        elif message == 'card':
            if phone_number in active_orders:
                active_orders[phone_number]['state'] = OrderStage.AWAITING_CARD
                # Create a pending order and store it
                pending_order = Order(phone_number, cart)
                pending_order.payment_method = 'card'
                active_orders[phone_number]['pending_order'] = pending_order
            
            return (
                "Please provide your card details in the format:\n"
                "CARD [16-digit number] [MM/YY] [CVV]\n"
                "Example: CARD 1234567890123456 12/25 123"
            )
        
        return (
            "Please choose a payment method:\n"
            "- Reply CASH for cash payment\n"
            "- Reply CARD for credit card"
        )

    def handle_card_payment(self, phone_number, message, active_orders, completed_orders):
        """Handle credit card payment processing"""
        if phone_number not in active_orders:
            return "No active order found. Please start a new order."
            
        if not message.upper().startswith('CARD '):
            return (
                "Please provide your card details in the format:\n"
                "CARD [16-digit number] [MM/YY] [CVV]\n"
                "Example: CARD 1234567890123456 12/25 123\n"
                "Or type BACK to choose a different payment method"
            )
        
        # Parse card details
        parts = message.split()
        if len(parts) != 4:
            return "Invalid format. Please use: CARD [number] [MM/YY] [CVV]"
        
        _, card_number, exp_date, cvv = parts
        
        # Validate card details
        is_valid, error_message = self.validate_card_details(card_number, exp_date, cvv)
        if not is_valid:
            return error_message
        
        # Get the pending order from active orders
        order = active_orders[phone_number].get('pending_order')
        if not order:
            # Create new order if none exists
            cart = active_orders[phone_number]['cart']
            order = Order(phone_number, cart)
            order.payment_method = 'card'
        
        # Move to completed orders
        if phone_number not in completed_orders:
            completed_orders[phone_number] = []
        
        completed_orders[phone_number].append(order)
        
        # Clear from active orders
        del active_orders[phone_number]
        
        return (
            f"Payment successful! Your total was ${order.total:.2f}. "
            f"Your order number is #{order.id}. "
            f"Your order will be ready at {order.estimated_ready.strftime('%I:%M %p')}."
        )

    def validate_card_details(self, card_number, exp_date, cvv):
        """Simple card validation"""
        try:
            # Basic format validation
            if not (card_number.isdigit() and len(card_number) == 16):
                return False, "Invalid card number. Please enter a 16-digit number."
            
            if not (cvv.isdigit() and len(cvv) == 3):
                return False, "Invalid CVV. Please enter a 3-digit number."
            
            # Basic expiration date validation
            month, year = exp_date.split('/')
            current_year = datetime.now().year % 100
            if not (1 <= int(month) <= 12 and int(year) >= current_year):
                return False, "Invalid expiration date. Please use MM/YY format with a future date."
            
            return True, "Card validated successfully"
        except Exception as e:
            return False, "Invalid card format. Please use: CARD [number] [MM/YY] [CVV]"

    def _handle_credit_card(self, order):
        return {
            'success': True,
            'message': (
                f"Total: ${order.total:.2f}\n"
                "Please reply with your card details in this format:\n"
                "CARD 1234567890123456 12/25 123"
            )
        }

    def _handle_cash(self, order):
        return {
            'success': True,
            'message': f"Perfect! Please pay ${order.total:.2f} when you pick up your order. Your order number is #{order.id}"
        }