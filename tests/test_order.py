import pytest
from src.core.order import OrderProcessor, OrderQueue
from src.core.cart import ShoppingCart
from src.core.enums import OrderStage

def test_handle_done_shows_cart_summary():
    # Setup
    processor = OrderProcessor()
    phone = "+1234567890"
    active_orders = {
        phone: {
            'cart': ShoppingCart(),
            'state': OrderStage.MENU,
            'order_queue': OrderQueue()
        }
    }
    
    # Add items to cart
    cart = active_orders[phone]['cart']
    cart.add_item({
        'item': 'Iced Latte',
        'price': 4.50,
        'modifiers': ['almond milk']
    })
    cart.add_item({
        'item': 'Muffin',
        'price': 3.00,
        'modifiers': []
    })

    # Test handle_done
    response = processor.handle_done(phone, active_orders)

    # Verify response contains cart summary and payment options
    assert "Iced Latte" in response
    assert "Muffin" in response
    assert "$8.25" in response  # Total with almond milk upcharge
    assert "How would you like to pay?" in response
    assert "CASH" in response
    assert "CARD" in response
    
    # Verify state transition
    assert active_orders[phone]['state'] == OrderStage.PAYMENT

def test_handle_done_empty_cart():
    processor = OrderProcessor()
    phone = "+1234567890"
    active_orders = {
        phone: {
            'cart': ShoppingCart(),
            'state': OrderStage.MENU,
            'order_queue': OrderQueue()
        }
    }

    response = processor.handle_done(phone, active_orders)
    assert "empty" in response.lower()
    