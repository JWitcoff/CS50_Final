from decimal import Decimal
from enum import Enum

class OrderStage(Enum):
    MENU = "menu"
    MODIFICATIONS = "modifications"
    CHECKOUT = "checkout"
    PAYMENT = "payment"
    AWAITING_CARD = "awaiting_card"
    COMPLETED = "completed"

MODIFIERS = {
    'milk': {
        'almond milk': Decimal('0.75'),
        'oat milk': Decimal('0.75'),
        'soy milk': Decimal('0.75')
    }
}

MENU = {
    1: {'item': 'Espresso', 'price': Decimal('3.50'), 'category': 'hot', 'description': 'Strong, pure coffee shot'},
    2: {'item': 'Latte', 'price': Decimal('4.50'), 'category': 'hot', 'description': 'latte with steamed milk'},
    3: {'item': 'Cappuccino', 'price': Decimal('4.50'), 'category': 'hot', 'description': 'Equal parts latte, steamed milk, and foam'},
    4: {'item': 'Cold Brew', 'price': Decimal('4.50'), 'category': 'cold', 'description': '12-hour steeped coffee'},
    5: {'item': 'Iced Latte', 'price': Decimal('4.50'), 'category': 'cold', 'description': 'latte over ice with cold milk'},
    6: {'item': 'Croissant', 'price': Decimal('3.50'), 'category': 'food', 'description': 'Butter croissant'},
    7: {'item': 'Muffin', 'price': Decimal('3.00'), 'category': 'food', 'description': 'Blueberry muffin'}
}

# Session timeout in minutes
SESSION_TIMEOUT = 30 