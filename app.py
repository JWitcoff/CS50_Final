# Standard library imports
from datetime import datetime, timedelta
import logging
import os
import uuid
import sys

# Third-party imports
from decouple import config
from dotenv import load_dotenv
from flask import Flask, request, render_template, jsonify
from openai import OpenAI
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import httpx

# Local/application imports
from src.core.dialogue import DialogueManager
from src.core.order import OrderProcessor
from src.core.payment import PaymentHandler

# Configuration Constants
PORT = int(os.getenv('PORT', 10000))
HOST = '0.0.0.0'

import logging
import os
from datetime import datetime
import sys

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging with both file and console output
log_filename = f"logs/coffee_shop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),  # Log to file
        logging.StreamHandler(sys.stdout)   # Log to console/stdout
    ],
    force=True  # This ensures our configuration takes effect
)

logger = logging.getLogger(__name__)
logger.info("=== Coffee Shop Application Starting ===")

# Menu and Modifier configurations
MODIFIERS = {
    'milk': {
        'almond milk': 0.75,
        'oat milk': 0.75,
        'soy milk': 0.75
    },
    'shots': {
        'extra shot': 1.00,
        'double shot': 1.50
    }
}

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure logging
log_filename = f"logs/coffee_shop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),  # Log to file
        logging.StreamHandler(sys.stdout)   # Log to console/stdout for Render
    ]
)
logger = logging.getLogger(__name__)

# Add startup log message
logger.info("=== Coffee Shop Application Starting ===")
logger.info(f"Environment: {os.getenv('FLASK_ENV', 'production')}")
logger.info(f"Port: {PORT}")

# Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize the OpenAI client
client = OpenAI(
    api_key=os.getenv('OPENAI_API_KEY')
)

# Menu configuration with formatted prices
MENU = {
    # Hot Drinks
    '1': {'item': 'Espresso', 'price': 3.50, 'category': 'hot', 'description': 'Strong, pure coffee shot'},
    '2': {'item': 'Latte', 'price': 4.50, 'category': 'hot', 'description': 'Espresso with steamed milk'},
    '3': {'item': 'Cappuccino', 'price': 4.50, 'category': 'hot', 'description': 'Equal parts espresso, steamed milk, and foam'},
    
    # Cold Drinks
    '4': {'item': 'Cold Brew', 'price': 4.50, 'category': 'cold', 'description': '12-hour steeped coffee'},
    '5': {'item': 'Iced Latte', 'price': 5.00, 'category': 'cold', 'description': 'Espresso over ice with cold milk'},
    
    # Food Items
    '6': {'item': 'Croissant', 'price': 3.50, 'category': 'food', 'description': 'Butter croissant'},
    '7': {'item': 'Muffin', 'price': 3.00, 'category': 'food', 'description': 'Blueberry muffin'}
}

# Initialize services
dialogue_manager = DialogueManager(menu=MENU, modifiers=MODIFIERS)
payment_handler = PaymentHandler()

# In-memory storage
active_orders = {}  # Stores current shopping sessions
completed_orders = {}  # Stores completed orders for tracking

class ShoppingCart:
    def __init__(self):
        self.items = []
        self.total = 0.00
        self.pending_modifier = None  # Track pending modifier that needs confirmation
        
    def add_item(self, item, quantity=1, modifiers=None):
        """Add an item to cart with optional modifiers"""
        for _ in range(quantity):
            item_copy = item.copy()  # Create a copy of the item
            if modifiers:
                item_copy['modifiers'] = modifiers
                # Add modifier costs to item price
                for mod in modifiers:
                    for mod_type, mod_prices in MODIFIERS.items():
                        if mod in mod_prices:
                            item_copy['price'] += mod_prices[mod]
            self.items.append(item_copy)
            self.total += item_copy['price']
            
    def remove_item(self, item_id):
        """Remove an item from cart"""
        for item in self.items:
            if str(item_id) in MENU and MENU[str(item_id)]['item'] == item['item']:
                self.items.remove(item)
                self.total -= item['price']
                return True
        return False
    
    def clear(self):
        """Clear the cart"""
        self.items = []
        self.total = 0.00
    
    def get_summary(self):
        """Get cart summary"""
        if not self.items:
            return "Your cart is empty. Text 'MENU' to see options."
        
        # Count quantities of each item
        items_count = {}
        for item in self.items:
            items_count[item['item']] = items_count.get(item['item'], 0) + 1
        
        # Format summary message with proper decimal places
        summary = "Your Cart:\n\n"
        for item_name, quantity in items_count.items():
            price = next(item['price'] for item in self.items if item['item'] == item_name)
            summary += f"{quantity}x {item_name} (${price:.2f} each)\n"
        
        summary += f"\nTotal: ${self.total:.2f}\n"
        summary += "\nReply with:\n"
        summary += "- ADD <number> to add more items\n"
        summary += "- REMOVE <number> to remove items\n"
        summary += "- DONE to checkout\n"
        summary += "- CLEAR to empty cart"
        
        return summary

class Order:
    def __init__(self, phone_number, cart):
        self.id = str(uuid.uuid4())[:8]  # Short unique ID
        self.phone_number = phone_number
        self.items = cart.items.copy()
        self.total = cart.total
        self.status = 'pending'
        self.created_at = datetime.now()
        self.estimated_ready = self.created_at + timedelta(minutes=15)
        
    def update_status(self, status):
        """Update order status"""
        self.status = status
        
    def get_status_message(self):
        """Get formatted status message"""
        status_emoji = {
            'pending': '⏳',
            'preparing': '👨‍🍳',
            'ready': '✅',
            'completed': '🎉',
            'cancelled': '❌'
        }
        
        message = f"Order #{self.id} Status: {status_emoji.get(self.status, '')} {self.status.upper()}\n\n"
        message += "Items:\n"
        
        items_count = {}
        for item in self.items:
            items_count[item['item']] = items_count.get(item['item'], 0) + 1
            
        for item_name, quantity in items_count.items():
            message += f"- {quantity}x {item_name}\n"
            
        message += f"\nTotal: ${self.total:.2f}\n"
        
        if self.status in ['pending', 'preparing']:
            message += f"\nEstimated ready: {self.estimated_ready.strftime('%I:%M %p')}"
            
        return message

def process_message(phone_number, message):
    """Process incoming messages based on current order state"""
    logger.info(f"Starting to process message for {phone_number}")
    logger.info(f"Raw message: {message}")
    message = message.lower().strip()
    logger.info(f"Processed message: {message}")
    
    # Add these debug statements
    logger.info(f"Current active_orders before processing: {active_orders}")
    logger.info(f"Current completed_orders before processing: {completed_orders}")
    
    # Get the current order state
    order = active_orders.get(phone_number, {})
    order_state = order.get('state', 'MENU')
    logger.info(f"Current order state: {order_state}")
    logger.info(f"Current active_orders: {active_orders}")

    # Initialize order if this is a new conversation
    if phone_number not in active_orders and message not in ['status', 'help']:
        logger.info(f"Initializing new order for {phone_number}")
        active_orders[phone_number] = {
            'state': 'MENU',
            'cart': ShoppingCart()
        }
        logger.info(f"Updated active_orders: {active_orders}")
        return get_menu_message()

    # Direct commands
    if message == 'menu' or message == 'start':
        logger.info("Sending menu message")
        return get_menu_message()

    # Handle card payment response
    if order_state == 'AWAITING_CARD':
        if message.startswith('card '):
            logger.info("Processing card payment")
            try:
                # Parse card details from message
                parts = message.split()
                if len(parts) != 4:
                    logger.warning("Invalid card format received")
                    return "Invalid format. Please use: CARD [number] [MM/YY] [CVV]"
                
                _, card_number, expiry, cvv = parts
                logger.info("Card details parsed successfully")
                
                # Validate card details
                is_valid, validation_message = payment_handler.validate_card_details(card_number, expiry, cvv)
                if not is_valid:
                    logger.warning(f"Card validation failed: {validation_message}")
                    return validation_message
                
                # Process successful payment and complete order
                cart = order.get('cart')
                if not cart or not cart.items:
                    logger.warning("Empty cart at checkout")
                    return "Your cart is empty. Please add items before checking out."
                
                logger.info("Processing order completion")
                confirmation = complete_order(phone_number, cart)
                del active_orders[phone_number]  # Clear the order after completion
                logger.info("Order completed successfully")
                return f"Payment successful! 🎉\n\n{confirmation}"
                
            except Exception as e:
                logger.error(f"Payment processing error: {str(e)}", exc_info=True)
                return "Invalid card format. Please use: CARD [number] [MM/YY] [CVV]"
        else:
            logger.info("Awaiting card payment - invalid format received")
            return "Please provide your card details in the format: CARD [number] [MM/YY] [CVV]"

    # Handle DONE command
    if message.lower() == 'done':
        if phone_number in active_orders and active_orders[phone_number]['cart'].items:
            cart = active_orders[phone_number]['cart']
            active_orders[phone_number]['state'] = 'AWAITING_CARD'
            return (
                f"Total: ${cart.total:.2f}\n\n"
                "To pay with card, reply with:\n"
                "CARD [16-digit number] [MM/YY] [CVV]\n"
                "Example: CARD 1234567890123456 12/25 123\n\n"
                "Or reply with CASH to pay at pickup"
            )
        return "Your cart is empty. Add some items first!"

    # Handle modifier confirmation
    if order_state == 'AWAITING_MOD_CONFIRM':
        if message in ['yes', 'y', 'ok', 'sure']:
            cart = order['cart']
            mod = cart.pending_modifier
            cart.add_item(order['pending_item'], modifiers=[mod])
            cart.pending_modifier = None
            order['state'] = 'MENU'
            return f"Added {order['pending_item']['item']} with {mod}!\n\n{cart.get_summary()}"
        elif message in ['no', 'n', 'cancel']:
            cart = order['cart']
            cart.pending_modifier = None
            order['state'] = 'MENU'
            return "Cancelled modification. Would you like to try something else?"

    # Handle direct commands
    if message == 'status':
        if phone_number in completed_orders and completed_orders[phone_number]:
            latest_order = completed_orders[phone_number][-1]
            return latest_order.get_status_message()
        return "No active orders found. Text 'START' to place an order."

    if message == 'help':
        return get_help_message()

    if message == 'clear':
        if phone_number in active_orders:
            active_orders[phone_number]['cart'].clear()
            return "Cart cleared. Text 'MENU' to see options."
        return "No active cart. Text 'START' to begin ordering."

    if message == 'cart':
        if phone_number in active_orders:
            return active_orders[phone_number]['cart'].get_summary()
        return "No active cart. Text 'START' to begin ordering."

    # Get AI response for general queries
    ai_response = dialogue_manager.get_ai_response(message, MENU, phone_number)
    if ai_response:
        # Process any order-related commands in the message
        order = active_orders.get(phone_number, {})
        cart = order.get('cart') if order else None

        # Check for item numbers or names in the message
        for menu_id, item in MENU.items():
            if menu_id in message or item['item'].lower() in message.lower():
                if cart:
                    cart.add_item(MENU[menu_id])
                    return f"{ai_response}\n\n{cart.get_summary()}"

        return ai_response

    # Fallback to menu
    return get_menu_message()

# Flask routes remain the same, but remove the stripe webhook route
@app.route('/sms', methods=['POST'])
def handle_sms():
    """Handle incoming SMS messages"""
    phone_number = request.values.get('From', '')
    message_body = request.values.get('Body', '').strip()
    
    logger.info(f"\n=== New Message ===")
    logger.info(f"From: {phone_number}")
    logger.info(f"Message: {message_body}")
    logger.info(f"Active Orders: {active_orders}")  # Add this to see current state
    
    resp = MessagingResponse()
    
    try:
        response_message = process_message(phone_number, message_body.lower())
        logger.info(f"Generated Response: {response_message}")
        resp.message(response_message)
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        error_msg = "Sorry, something went wrong. Please text 'START' to try again."
        logger.info(f"Error Response: {error_msg}")
        resp.message(error_msg)
    
    logger.info(f"Final Response: {str(resp)}")
    logger.info("=== End Message ===\n")
    return str(resp)

@app.route('/', methods=['GET'])
def home():
    """Handle requests to the root URL"""
    return render_template('index.html', 
                         twilio_number=TWILIO_PHONE_NUMBER,
                         menu=MENU)

@app.route('/health')
def health_check():
    return 'OK', 200

def complete_order(phone_number, cart):
    """Complete an order and set up tracking"""
    logger.info(f"Creating new order for {phone_number} with {len(cart.items)} items")
    
    # Create new order with status and tracking
    order = Order(phone_number, cart)
    
    # Store order in completed orders
    if phone_number not in completed_orders:
        completed_orders[phone_number] = []
    completed_orders[phone_number].append(order)
    
    logger.info(f"Created order {order.id} for {phone_number}")
    
    # Generate detailed confirmation message
    items_summary = "\n".join([f"- {item['item']}" + 
                             (f" with {', '.join(item['modifiers'])}" if 'modifiers' in item and item['modifiers'] else "")
                             for item in cart.items])
    
    confirmation_message = (
        f"🎉 Order #{order.id} confirmed!\n\n"
        f"Items:\n{items_summary}\n\n"
        f"Total paid: ${cart.total:.2f}\n\n"
        f"Estimated ready time: {order.estimated_ready.strftime('%I:%M %p')}\n\n"
        "Text 'STATUS' anytime to check your order.\n"
        "Text 'START' to place another order."
    )
    
    return confirmation_message

def get_help_message():
    """Generate help message with available commands"""
    return( 
        "CS50 Coffee Shop Commands:\n\n"
        "🛒 Ordering:\n"
        "- Order by number (e.g., '1' for Espresso)\n"
        "- Order by name (e.g., 'Espresso')\n"
        "- Or use 'ADD 1' format\n\n"
        "📋 Menu:\n"
        "- START: Begin ordering\n"
        "- MENU: See full menu\n"
        "- HOT: View hot drinks\n"
        "- COLD: View cold drinks\n"
        "- FOOD: View food items\n"
        "- FIND [term]: Search menu\n\n"
        "🛍️ Cart:\n"
        "- CART: View your cart\n"
        "- CLEAR: Empty cart\n"
        "- DONE: Proceed to checkout\n\n"
        "📦 Order:\n"
        "- STATUS: Check your order status\n\n"
        "Need help? Visit our website or call us at (555) 123-4567"
    )

def get_menu_message():
    """Generate the menu message"""
    message = "Welcome to Coffee S50! Order by number or name:\n\n"
    for key, item in MENU.items():
        message += f"{key}. {item['item']} (${item['price']:.2f})\n"
        message += f"   {item['description']}\n"
    return message

if __name__ == '__main__':
    logger.info(f"Starting application on {HOST}:{PORT}")
    logger.info(f"Environment: {os.getenv('FLASK_ENV', 'production')}")
    app.run(host=HOST, port=PORT, debug=True)
