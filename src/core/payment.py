import stripe
from src.core.state import OrderContext
from src.core.enums import OrderStage
import os
import logging

logger = logging.getLogger(__name__)

class PaymentHandler:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
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
            'message': "I'm sorry, I didn't recognize that payment method. Would you like to pay with credit card or cash?"
        }

    def _handle_credit_card(self, order):
        try:
            # Create a PaymentIntent instead of a Checkout Session
            payment_intent = stripe.PaymentIntent.create(
                amount=int(order.total * 100),  # Convert to cents
                currency='usd',
                metadata={
                    'order_id': order.id,
                    'phone_number': order.phone_number
                },
                payment_method_types=['card']
            )

            return {
                'success': True,
                'payment_intent_id': payment_intent.id,
                'message': (
                    "Please reply with your credit card number, expiration date (MM/YY), "
                    "and CVV in this format: CARD 4242424242424242 12/25 123"
                )
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return {
                'success': False,
                'message': "Sorry, there was an error processing your payment. Please try again."
            }

    def _handle_cash(self, order):
        return {
            'success': True,
            'message': f"Perfect! Please pay ${order.total:.2f} when you pick up your order. Your order number is #{order.id}"
        }

    def confirm_card_payment(self, payment_intent_id, card_details):
        """Process the actual card payment once details are received"""
        try:
            payment_method = stripe.PaymentMethod.create(
                type='card',
                card={
                    'number': card_details['number'],
                    'exp_month': card_details['exp_month'],
                    'exp_year': card_details['exp_year'],
                    'cvc': card_details['cvc']
                }
            )

            payment_intent = stripe.PaymentIntent.confirm(
                payment_intent_id,
                payment_method=payment_method.id
            )

            if payment_intent.status == 'succeeded':
                return {
                    'success': True,
                    'message': "Payment successful! Your order is being prepared."
                }
            else:
                return {
                    'success': False,
                    'message': "Payment failed. Please try again or use a different card."
                }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error during confirmation: {str(e)}")
            return {
                'success': False,
                'message': "Sorry, there was an error processing your payment. Please try again."
            }

    def validate_payment(self, payment_details):
        # This will be updated when we integrate Stripe
        return True