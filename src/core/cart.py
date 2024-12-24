from dataclasses import dataclass, field
from typing import List, Dict, Optional
from decimal import Decimal

@dataclass
class CartItem:
    name: str
    price: Decimal
    quantity: int = 1
    modifiers: List[str] = field(default_factory=list)
    category: str = ''
    description: str = ''

class ShoppingCart:
    def __init__(self):
        self.items: List[CartItem] = []
        self.pending_modifier: Optional[str] = None
        self._total: Decimal = Decimal('0')

    def add_item(self, menu_item: Dict, quantity: int = 1, modifiers: List[str] = None):
        """Add item to cart with modifiers"""
        modifiers = modifiers or []
        
        # Calculate modified price
        base_price = Decimal(str(menu_item['price']))
        modifier_price = Decimal('0.75') * len(modifiers)  # $0.75 per modifier
        total_price = base_price + modifier_price

        # Create new cart item
        new_item = CartItem(
            name=menu_item['item'],
            price=total_price,
            quantity=quantity,
            modifiers=modifiers,
            category=menu_item.get('category', ''),
            description=menu_item.get('description', '')
        )
        
        # Check if identical item exists
        for item in self.items:
            if (item.name == new_item.name and 
                item.price == new_item.price and 
                sorted(item.modifiers) == sorted(new_item.modifiers)):
                item.quantity += quantity
                break
        else:
            self.items.append(new_item)

        self._update_total()

    def remove_item(self, index: int, quantity: int = 1) -> bool:
        """Remove item(s) from cart"""
        if 0 <= index < len(self.items):
            if self.items[index].quantity <= quantity:
                del self.items[index]
            else:
                self.items[index].quantity -= quantity
            self._update_total()
            return True
        return False

    def clear(self):
        """Clear all items from cart"""
        self.items = []
        self._update_total()

    def _update_total(self):
        """Update cart total"""
        self._total = sum(item.price * item.quantity for item in self.items)

    def get_total(self) -> Decimal:
        """Get cart total"""
        return self._total

    def get_summary(self) -> str:
        """Get formatted cart summary"""
        if not self.items:
            return "Your cart is empty!"

        summary = ["Your Cart:"]
        for item in self.items:
            mod_text = f" with {', '.join(item.modifiers)}" if item.modifiers else ""
            summary.append(f"{item.quantity}x {item.name}{mod_text} (${item.price:.2f} each)")
        
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