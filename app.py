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
from fuzzywuzzy import fuzz
from openai import OpenAI
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import httpx

# Local/application imports
from src.core.dialogue import DialogueManager
from src.core.order import OrderProcessor, OrderQueue
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
    
    # Handle MENU command in any state
    if message == 'menu':
        return get_menu_message()
        
    # Handle START command
    if message == 'start':
        session = session_manager.create_session(phone_number)
        active_orders[phone_number] = {
            'state': OrderStage.MENU,
            'cart': ShoppingCart(),
            'order_queue': OrderQueue(),
            'pending_items': []
        }
        return get_menu_message()
        
    # Check if user has an active order
    if phone_number not in active_orders:
        return "Please text 'START' to begin ordering."
        
    order = active_orders[phone_number]
    current_state = order['state']
    logger.info(f"Current state for {phone_number}: {current_state}")
    
    # Get or create customer context
    if phone_number not in customer_contexts:
        customer_contexts[phone_number] = CustomerContext()
    customer_context = customer_contexts[phone_number]
    
    # Create cart context for responses
    cart_context = get_cart_context(order['cart'], order)
    
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
            return conversation_handler.get_friendly_response(
                "How would you like to pay? Reply with CASH or CARD.",
                customer_context,
                cart=cart_context
            )

    # Try handling casual conversation first
    casual_response = conversation_handler.handle_chat(message, cart=cart_context)
    if casual_response and message not in ['menu', 'start']:
        return casual_response
    
    # Handle AWAITING_MOD_CONFIRM state
    if current_state == OrderStage.AWAITING_MOD_CONFIRM:
        has_modifier, modifier = menu_handler.check_for_modification(message)
        if has_modifier:
            order['pending_modifier'] = modifier
            return conversation_handler.get_friendly_response(
                f"{modifier} costs $0.75 extra. Reply YES to confirm or NO for regular milk.",
                customer_context,
                cart=cart_context
            )
            
        if menu_handler.is_confirmation(message):
            if 'pending_modifier' in order:
                order['cart'].add_item(order['pending_item'], modifiers=[order['pending_modifier']])
                customer_context.usual_modifications.append(order['pending_modifier'])
            else:
                order['cart'].add_item(order['pending_item'])
                
            # Update cart context after adding item
            cart_context = get_cart_context(order['cart'], order)
                
            # Process next pending item if any exist
            if order['pending_items']:
                next_item = order['pending_items'].pop(0)
                order['pending_item'] = next_item
                cart_context['pending_item'] = next_item
                
                if next_item.get('modifiers'):
                    mod = next_item['modifiers'][0]
                    order['pending_modifier'] = mod
                    return conversation_handler.get_friendly_response(
                        f"{mod} costs $0.75 extra. Reply YES to confirm or NO for regular milk.",
                        customer_context,
                        cart=cart_context
                    )
                elif next_item['category'] in ['hot', 'cold']:
                    return conversation_handler.get_friendly_response(
                        "Would you like any milk modifications?",
                        customer_context,
                        cart=cart_context
                    )
            
            # If no more pending items, return to menu state
            order['state'] = OrderStage.MENU
            order['pending_item'] = None
            return conversation_handler.get_friendly_response(
                order['cart'].get_summary(),
                customer_context,
                cart=cart_context,
                item_added=True
            )
            
        if menu_handler.is_denial(message):
            order['cart'].add_item(order['pending_item'])
            cart_context = get_cart_context(order['cart'], order)
            
            # Process next pending item if any exist
            if order['pending_items']:
                next_item = order['pending_items'].pop(0)
                order['pending_item'] = next_item
                cart_context['pending_item'] = next_item
                
                if next_item.get('modifiers'):
                    mod = next_item['modifiers'][0]
                    order['pending_modifier'] = mod
                    return conversation_handler.get_friendly_response(
                        f"{mod} costs $0.75 extra. Reply YES to confirm or NO for regular milk.",
                        customer_context,
                        cart=cart_context
                    )
                elif next_item['category'] in ['hot', 'cold']:
                    return conversation_handler.get_friendly_response(
                        "Would you like any milk modifications?",
                        customer_context,
                        cart=cart_context
                    )
                    
            order['state'] = OrderStage.MENU
            order['pending_item'] = None
            return conversation_handler.get_friendly_response(
                order['cart'].get_summary(),
                customer_context,
                cart=cart_context
            )
            
        return conversation_handler.get_friendly_response(
            "Please choose a milk type or reply NO for regular milk",
            customer_context,
            cart=cart_context
        )
    
    # Handle menu state
    if current_state == OrderStage.MENU:
        # Extract menu items and modifiers
        found_items = menu_handler.extract_menu_items_and_modifiers(message)
        if found_items:
            items_needing_mods = []
            non_mod_items = []
            
            # First sort items into modifiable and non-modifiable
            for item in found_items:
                if item.get('modifiers') or item['category'] in ['hot', 'cold']:
                    items_needing_mods.append(item)
                    logger.info(f"Queuing item for modification: {item['item']}")
                else:
                    non_mod_items.append(item)
                    logger.info(f"Adding non-modifiable item: {item['item']}")
            
            # Add all non-modifiable items to cart first
            for item in non_mod_items:
                order['cart'].add_item(item)
                logger.info(f"Added to cart: {item['item']}")
            
            # Update cart context after adding non-modifiable items
            cart_context = get_cart_context(order['cart'], order)
            
            # If we have items needing mods, handle the first one
            if items_needing_mods:
                item = items_needing_mods.pop(0)
                order['pending_item'] = item
                order['pending_items'] = items_needing_mods  # Store remaining items
                cart_context['pending_item'] = item
                cart_context['pending_items'] = items_needing_mods
                
                order['state'] = OrderStage.AWAITING_MOD_CONFIRM
                
                # Handle specific modifiers if present
                if item.get('modifiers'):
                    mod = item['modifiers'][0]
                    order['pending_modifier'] = mod
                    return conversation_handler.get_friendly_response(
                        f"{mod} costs $0.75 extra. Reply YES to confirm or NO for regular milk.",
                        customer_context,
                        cart=cart_context
                    )
                else:
                    # No specific modifier requested, ask for preferences
                    if customer_context.usual_modifications:
                        usual_mod = customer_context.usual_modifications[-1]
                        return conversation_handler.get_friendly_response(
                            f"Would you like your usual {usual_mod}?",
                            customer_context,
                            cart=cart_context
                        )
                    return conversation_handler.get_friendly_response(
                        "Would you like any milk modifications?",
                        customer_context,
                        cart=cart_context
                    )
            
            # If no items need modification, just show cart summary
            return conversation_handler.get_friendly_response(
                order['cart'].get_summary(),
                customer_context,
                cart=cart_context,
                items_added=True
            )
        
        return conversation_handler.get_friendly_response(
            "I didn't recognize those items. Would you like to see our menu?",
            customer_context,
            cart=cart_context,
            menu_prompt=True
        )
    
    # Handle payment state
    if current_state == OrderStage.PAYMENT:
        if message.lower() in ['cash', 'card']:
            response = payment_handler.handle_payment(phone_number, message, active_orders, completed_orders)
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
    app.run(host=HOST, port=PORT, debug=True)