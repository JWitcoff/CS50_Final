import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PaymentHandler:
    def __init__(self):
        self.payment_methods = {
            'credit': self._handle_credit_card,
            'card': self._handle_credit_card,
            'cash': self._handle_cash
        }

    def process_payment(self, order, payment_method):
        payment_method = payment_method.lower()
        for key, handler in self.payment_methods.items():
            if key in payment_method:
                return handler(order)
        return {
            'success': False,
            'message': "Would you like to pay with credit card or cash?"
        }

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
            logger.error(f"Card validation error: {str(e)}")
            return False, "Invalid card format. Please use: CARD [number] [MM/YY] [CVV]"