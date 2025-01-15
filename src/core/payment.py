import uuid
from datetime import datetime
from src.core.enums import OrderStage

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
        
        if message == 'cash':
            if phone_number not in active_orders:
                return "No active order found. Please start a new order."
                
            cart = active_orders[phone_number]['cart']
            order_id = str(uuid.uuid4())[:8]
            
            # Move to completed orders
            if phone_number not in completed_orders:
                completed_orders[phone_number] = []
            
            completed_orders[phone_number].append({
                'cart': cart,
                'order_id': order_id,
                'timestamp': datetime.now(),
                'payment_method': 'cash'
            })
            
            # Store total before removing active order
            total = cart.get_total()
            
            # Clear from active orders
            del active_orders[phone_number]
            
            return (
                f"Great choice! 😊 Please pay ${total:.2f} when you pick up your order. "
                f"Your order number is #{order_id}. It'll be ready in about 15 minutes. Enjoy your treats!"
            )
        
        elif message == 'card':
            if phone_number in active_orders:
                active_orders[phone_number]['state'] = OrderStage.AWAITING_CARD
            return (
                "Please provide your card details in the format:\n"
                "CARD [16-digit number] [MM/YY] [CVV]\n"
                "Example: CARD 1234567890123456 12/25 123"
            )
        
        # Default case if neither cash nor card
        return (
            "Please choose a payment method:\n"
            "- Reply CASH for cash payment\n"
            "- Reply CARD for credit card"
        )

    def handle_card_payment(self, phone_number, message, active_orders, completed_orders):
        """Handle credit card payment processing"""
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
        
        if phone_number not in active_orders:
            return "No active order found. Please start a new order."
            
        # Process payment (in real app, would integrate with payment processor)
        cart = active_orders[phone_number]['cart']
        order_id = str(uuid.uuid4())[:8]
        total = cart.get_total()
        
        # Move to completed orders
        if phone_number not in completed_orders:
            completed_orders[phone_number] = []
        
        completed_orders[phone_number].append({
            'cart': cart,
            'order_id': order_id,
            'timestamp': datetime.now(),
            'payment_method': 'card'
        })
        
        # Clear from active orders
        del active_orders[phone_number]
        
        return (
            f"Payment successful! Your total was ${total:.2f}. "
            f"Your order number is #{order_id}. "
            "Your order will be ready in about 15 minutes."
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
    