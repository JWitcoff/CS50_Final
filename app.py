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
from src.core.enums import OrderStage
from src.core.session import SessionManager
from src.core.config import MENU, MODIFIERS
from src.core.cart import ShoppingCart, CartItem

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

# Initialize services
dialogue_manager = DialogueManager(menu=MENU, modifiers=MODIFIERS)
payment_handler = PaymentHandler()
order_processor = OrderProcessor()

# In-memory storage
active_orders = {}  # Stores current shopping sessions
completed_orders = {}  # Stores completed orders for tracking

# Initialize session manager
session_manager = SessionManager()

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

def classify_confirmation(message):
    """Use OpenAI to classify if a message is confirmatory"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a binary classifier for user intent. 
                Respond ONLY with 'yes' or 'no'.
                Determine if the following message indicates agreement, confirmation, or wanting to proceed.
                Examples:
                'yeah sure' -> 'yes'
                'nah thanks' -> 'no'
                'sounds good!' -> 'yes'
                'i guess so' -> 'yes'
                'not really' -> 'no'"""},
                {"role": "user", "content": message}
            ],
            temperature=0.3,  # Lower temperature for more consistent responses
            max_tokens=1
        )
        result = response.choices[0].message.content.strip().lower() == 'yes'
        logger.info(f"Intent classification for '{message}': {result}")
        return result
    except Exception as e:
        logger.error(f"OpenAI classification error: {str(e)}")
        # Fall back to simple word matching if API fails
        fallback = message.lower().strip('!.,') in ['yes', 'yeah', 'sure', 'ok']
        logger.info(f"Falling back to simple classification for '{message}': {fallback}")
        return fallback

def extract_menu_items(message):
    """Extract all menu items from a message"""
    found_items = []
    for menu_id, item in MENU.items():
        if item['item'].lower() in message.lower():
            found_items.append(item)
    return found_items

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

def process_message(phone_number, message):
    """Process incoming messages based on current order state"""
    logger.info(f"Starting to process message for {phone_number}")
    logger.info(f"Raw message: {message}")
    message = message.lower().strip()
    logger.info(f"Processed message: {message}")
    
    # Add these debug statements
    logger.info(f"Current active_orders before processing: {active_orders}")
    logger.info(f"Current completed_orders before processing: {completed_orders}")
    
    # Handle START command
    if message == 'start':
        # Initialize new order
        active_orders[phone_number] = {
            'state': OrderStage.MENU,
            'cart': ShoppingCart(),
            'order_queue': OrderQueue()
        }
        session_manager.update_session_state(phone_number, OrderStage.MENU)
        return get_menu_message()  # Return the menu message
    
    # Initialize or get session state
    current_state = session_manager.get_session_state(phone_number)
    
    # Initialize new order if needed
    if phone_number not in active_orders:
        active_orders[phone_number] = {
            'state': OrderStage.MENU,
            'cart': ShoppingCart(),
            'order_queue': OrderQueue()
        }
        session_manager.update_session_state(phone_number, OrderStage.MENU)

    # Handle checkout command
    if message.lower() in ['done', 'checkout', 'pay']:
        if phone_number in active_orders:
            cart = active_orders[phone_number]['cart']
            if not cart.items:
                return "Your cart is empty! Please add items before checking out."
            
            # Update to payment state
            session_manager.update_session_state(phone_number, OrderStage.PAYMENT)
            active_orders[phone_number]['state'] = OrderStage.PAYMENT
            
            return (
                f"Total: ${cart.get_total():.2f}\n"
                "How would you like to pay?\n"
                "Reply with:\n"
                "- CASH for cash payment\n"
                "- CARD to pay by credit card"
            )

    # Handle payment method selection
    if current_state == OrderStage.PAYMENT:
        if message.lower() == 'cash':
            cart = active_orders[phone_number]['cart']
            order_id = str(uuid.uuid4())[:8]
            
            # Move to completed state
            session_manager.update_session_state(phone_number, OrderStage.COMPLETED)
            completed_orders[phone_number] = active_orders[phone_number]
            del active_orders[phone_number]
            
            return (
                f"Perfect! Please pay ${cart.get_total():.2f} when you pick up your order.\n"
                f"Your order number is #{order_id}\n"
                "Your order will be ready in about 15 minutes."
            )
            
        elif message.lower() == 'card':
            session_manager.update_session_state(phone_number, OrderStage.AWAITING_CARD)
            active_orders[phone_number]['state'] = OrderStage.AWAITING_CARD
            return (
                "Please provide your card details in the format:\n"
                "CARD [16-digit number] [MM/YY] [CVV]\n"
                "Example: CARD 1234567890123456 12/25 123"
            )
            
        else:
            return (
                "Please choose your payment method:\n"
                "- Reply CASH for cash payment\n"
                "- Reply CARD for credit card"
            )

    # Handle card details
    if current_state == OrderStage.AWAITING_CARD:
        if message.lower() == 'back':
            session_manager.update_session_state(phone_number, OrderStage.PAYMENT)
            active_orders[phone_number]['state'] = OrderStage.PAYMENT
            return (
                "How would you like to pay?\n"
                "Reply with:\n"
                "- CASH for cash payment\n"
                "- CARD to pay by credit card"
            )
            
        if message.upper().startswith('CARD'):
            try:
                parts = message.split()
                if len(parts) != 4:
                    raise ValueError("Invalid format")
                
                _, card_number, exp_date, cvv = parts
                # Process card payment...
                
                cart = active_orders[phone_number]['cart']
                order_id = str(uuid.uuid4())[:8]
                
                # Move to completed state
                session_manager.update_session_state(phone_number, OrderStage.COMPLETED)
                completed_orders[phone_number] = active_orders[phone_number]
                del active_orders[phone_number]
                
                return (
                    f"Payment processed successfully!\n"
                    f"Your order number is #{order_id}\n"
                    f"Total paid: ${cart.get_total():.2f}\n"
                    "Your order will be ready in about 15 minutes."
                )
            except Exception as e:
                return (
                    "Invalid card format. Please use:\n"
                    "CARD [16-digit number] [MM/YY] [CVV]\n"
                    "Example: CARD 1234567890123456 12/25 123\n"
                    "Or type BACK to choose a different payment method"
                )

    # Extract all menu items from message
    found_items = extract_menu_items(message)
    if found_items:
        # Store all found items in the queue
        active_orders[phone_number]['order_queue'].add_items(found_items)
        
        # Process first item if not in middle of another operation
        if active_orders[phone_number]['state'] == 'MENU':
            return process_next_item(phone_number)

def process_next_item(phone_number):
    """Process next item in the queue"""
    order = active_orders[phone_number]
    queue = order['order_queue']
    
    if not queue.has_more():
        return order['cart'].get_summary()
        
    next_item = queue.get_next()
    
    # Check if item needs modifier
    if next_item['category'] in ['hot', 'cold']:
        # Store original message context
        order['pending_item'] = next_item
        order['state'] = 'AWAITING_MOD_CONFIRM'
        
        return (f"Would you like {next_item['item']} with any modifications?\n"
                "Available options: almond milk, oat milk, soy milk (+$0.75 each)")
    else:
        # Add non-drink items directly to cart
        order['cart'].add_item(next_item)
        return process_next_item(phone_number)

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
