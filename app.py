# Standard library imports
from datetime import datetime, timedelta
import logging
import os
import uuid
import sys
from decimal import Decimal
from typing import List, Dict, Tuple, Optional

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
from src.core.order import OrderProcessor, OrderQueue, Order
from src.core.payment import PaymentHandler
from src.core.enums import OrderStage
from src.core.session import SessionManager
from src.core.config import MENU, MODIFIERS
from src.core.cart import ShoppingCart, CartItem
from src.core.menu_handler import MenuHandler
from src.core.state import CustomerContext, OrderContext
from src.core.conversation_handler import ConversationHandler

# Configuration Constants
PORT = int(os.getenv('PORT', 10000))
HOST = '0.0.0.0'

# Configure logging
os.makedirs('logs', exist_ok=True)
log_filename = f"logs/coffee_shop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
logger.info("=== Coffee Shop Application Starting ===")

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')

# Initialize services
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
dialogue_manager = DialogueManager(menu=MENU, modifiers=MODIFIERS)
payment_handler = PaymentHandler()
order_processor = OrderProcessor()
session_manager = SessionManager()
menu_handler = MenuHandler(menu=MENU, modifiers=MODIFIERS)
conversation_handler = ConversationHandler(openai_client)

# In-memory storage
active_orders = {}
completed_orders = {}
customer_contexts = {}

def get_menu_message():
    """Generate the menu message"""
    message = "Welcome to Coffee S50! Order by number or name:\n\n"
    for key, item in MENU.items():
        message += f"{key}. {item['item']} (${item['price']:.2f})\n"
        message += f"   {item['description']}\n"
    return message

def get_cart_context(cart: ShoppingCart, order_state: Dict) -> Dict:
    """Get formatted cart context for dialogue manager"""
    cart_info = {
        'items': [
            {
                'name': item.name,
                'quantity': item.quantity,
                'modifiers': item.modifiers,
                'price': float(item.price)
            } for item in cart.items
        ],
        'total': float(cart.get_total()),
        'pending_items': order_state.get('pending_items', []),
        'pending_item': order_state.get('pending_item')
    }
    logger.info(f"Cart context: {cart_info}")
    return cart_info

def process_message(phone_number, message):
    """Process incoming messages based on current order state"""
    message = message.lower().strip()
    logger.info(f"Processing message: {message} from {phone_number}")
    
    # Update or get session state
    session = session_manager.get_session(phone_number)
    current_state = session['state']
    logger.info(f"Session state for {phone_number}: {current_state}")
    
    # Handle MENU command in any state
    if message == 'menu':
        return get_menu_message()
        
    # Handle START command
    if message == 'start':
        active_orders[phone_number] = {
            'state': OrderStage.MENU,
            'cart': ShoppingCart(),
            'order_queue': OrderQueue(),
            'pending_items': []
        }
        session_manager.update_session_state(phone_number, OrderStage.MENU)
        return get_menu_message()
        
    # Check if user has an active order
    if phone_number not in active_orders:
        return "Please text 'START' to begin ordering."
    
    order = active_orders[phone_number]
    
    # Sync session state with order state
    if order['state'] != current_state:
        session_manager.update_session_state(phone_number, order['state'])
    
    # Get or create customer context
    if phone_number not in customer_contexts:
        customer_contexts[phone_number] = CustomerContext()
    customer_context = customer_contexts[phone_number]
    
    # Create cart context for responses
    cart_context = get_cart_context(order['cart'], order)
    
    # Handle items in OrderQueue if any exist
    if order['order_queue'].has_more():
        next_item_response = order_processor.process_next_item(phone_number, active_orders)
        if next_item_response:
            return conversation_handler.get_friendly_response(
                next_item_response,
                customer_context,
                cart=cart_context
            )
    
    # Handle cart inquiry
    if message.lower() in ['what did i order', 'what\'s in my cart', 'show cart']:
        return conversation_handler.get_friendly_response(
            order['cart'].get_summary(),
            customer_context,
            cart=cart_context
        )
    
    # Handle checkout commands in MENU state
    if current_state == OrderStage.MENU:
        checkout_commands = ['done', 'checkout', 'pay', "let's checkout", 'check out']
        if any(cmd in message.lower() for cmd in checkout_commands):
            if order['cart'].is_empty():
                return "Your cart is empty! Please add items before checking out."
            if order.get('pending_items'):
                logger.info("Items pending modification during checkout attempt")
                return conversation_handler.get_friendly_response(
                    "You have items waiting for modification. Please complete those first.",
                    customer_context,
                    cart=cart_context
                )
            order['state'] = OrderStage.PAYMENT
            session_manager.update_session_state(phone_number, OrderStage.PAYMENT)
            return conversation_handler.get_friendly_response(
                "How would you like to pay? Reply with CASH or CARD.",
                customer_context,
                cart=cart_context
            )

    # Try handling casual conversation first
    casual_response = conversation_handler.handle_chat(message, cart=cart_context)
    if casual_response and message not in ['menu', 'start']:
        return casual_response

    # Rest of your existing process_message function stays the same until payment handling
    
    # Handle payment state
    if current_state == OrderStage.PAYMENT:
        if message.lower() in ['cash', 'card']:
            response = payment_handler.handle_payment(phone_number, message, active_orders, completed_orders)
            if message.lower() == 'card':
                session_manager.update_session_state(phone_number, OrderStage.AWAITING_CARD)
            return conversation_handler.get_friendly_response(
                response, 
                customer_context, 
                cart=cart_context,
                payment=True
            )
        return conversation_handler.get_friendly_response(
            "Please choose your payment method",
            customer_context,
            cart=cart_context
        )
    
    # Handle card payment state
    if current_state == OrderStage.AWAITING_CARD:
        response = payment_handler.handle_card_payment(phone_number, message, active_orders, completed_orders)
        if response.startswith("Thanks!"):  # Payment successful
            session_manager.update_session_state(phone_number, OrderStage.COMPLETED)
        return conversation_handler.get_friendly_response(
            response, 
            customer_context, 
            cart=cart_context,
            payment=True
        )
    
    return conversation_handler.get_friendly_response(
        "I'm not sure what to do. Would you like to start a new order?",
        customer_context,
        cart=cart_context,
        confused=True
    )

@app.route('/sms', methods=['POST'])
def handle_sms():
    """Handle incoming SMS messages"""
    phone_number = request.values.get('From', '')
    message_body = request.values.get('Body', '').strip()
    
    logger.info(f"\n=== New Message ===")
    logger.info(f"From: {phone_number}")
    logger.info(f"Message: {message_body}")
    
    resp = MessagingResponse()
    
    try:
        response_message = process_message(phone_number, message_body)
        logger.info(f"Generated Response: {response_message}")
        resp.message(response_message)
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        resp.message("Sorry, something went wrong. Please text 'START' to try again.")
    
    logger.info(f"Final Response: {str(resp)}")
    logger.info("=== End Message ===")
    return str(resp)

@app.route('/')
def home():
    return render_template('index.html', 
                         twilio_number=TWILIO_PHONE_NUMBER,
                         menu=MENU)

@app.route('/health')
def health_check():
    return 'OK', 200

if __name__ == '__main__':
    app.run(host=HOST, port=PORT)