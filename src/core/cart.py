from dataclasses import dataclass, field
from typing import List, Dict, Optional
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

@dataclass
class CartItem:
    name: str
    price: Decimal
    quantity: int = 1
    modifiers: List[str] = field(default_factory=list)
    category: str = ''
    description: str = ''

    def get_total_price(self) -> Decimal:
        """Calculate total price including modifiers"""
        modifier_price = Decimal('0.75') * len(self.modifiers)
        return (self.price + modifier_price) * self.quantity

class ShoppingCart:
    def __init__(self):
        self.items: List[CartItem] = []
        self.pending_modifier: Optional[str] = None
        self._total: Decimal = Decimal('0')
        logger.info("New shopping cart created")
        
    def add_item(self, menu_item: Dict, quantity: int = 1, modifiers: List[str] = None):
        """Add item to cart with modifiers"""
        modifiers = modifiers or []
        # Debug logging
        logger.info(f"Adding to cart: {menu_item['item']} with modifiers: {modifiers}")
        logger.info(f"Current cart contents before add: {[f'{item.name} (x{item.quantity})' for item in self.items]}")
        
        base_price = Decimal(str(menu_item['price']))
        new_item = CartItem(
            name=menu_item['item'],
            price=base_price,
            quantity=quantity,
            modifiers=modifiers,
            category=menu_item.get('category', ''),
            description=menu_item.get('description', '')
        )
        
        # Check if identical item exists
        for item in self.items:
            if (item.name == new_item.name and
                sorted(item.modifiers) == sorted(new_item.modifiers)):
                item.quantity += quantity
                logger.info(f"Updated existing item quantity. {item.name} now has quantity {item.quantity}")
                break
        else:
            self.items.append(new_item)
            logger.info(f"Added new item to cart: {new_item.name}")
        
        self._update_total()
        logger.info(f"Cart contents after add: {[f'{item.name} (x{item.quantity})' for item in self.items]}")
        logger.info(f"Cart total is now: ${self._total}")

    def remove_item(self, index: int, quantity: int = 1) -> bool:
        """Remove item(s) from cart"""
        if 0 <= index < len(self.items):
            logger.info(f"Removing {quantity}x {self.items[index].name} from cart")
            if self.items[index].quantity <= quantity:
                del self.items[index]
                logger.info("Item completely removed from cart")
            else:
                self.items[index].quantity -= quantity
                logger.info(f"Item quantity reduced to {self.items[index].quantity}")
            self._update_total()
            return True
        logger.info("Remove item failed: invalid index")
        return False

    def clear(self):
        """Clear all items from cart"""
        logger.info("Clearing cart")
        self.items = []
        self._update_total()

    def _update_total(self):
        """Update cart total"""
        self._total = sum(item.get_total_price() for item in self.items)
        logger.info(f"Cart total updated to: ${self._total}")

    def get_total(self) -> Decimal:
        """Get cart total"""
        return self._total

    def get_summary(self) -> str:
        """Get formatted cart summary"""
        if not self.items:
            return "Your cart is empty!"
        
        logger.info("Generating cart summary")
        summary = ["Your Cart:"]
        for item in self.items:
            mod_text = f" with {', '.join(item.modifiers)}" if item.modifiers else ""
            item_price = item.get_total_price() / item.quantity
            summary.append(f"{item.quantity}x {item.name}{mod_text} (${item_price:.2f} each)")
        summary.append(f"Total: ${self.get_total():.2f}")
        
        summary.append("\nReply with:")
        summary.append("- ADD <number> to add more items")
        summary.append("- REMOVE <number> to remove items")
        summary.append("- DONE to checkout")
        summary.append("- CLEAR to empty cart")
        
        return "\n".join(summary)

    def is_empty(self) -> bool:
        """Check if cart is empty"""
        return len(self.items) == 0
    