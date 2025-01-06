from enum import Enum
from dataclasses import dataclass
from typing import List, Dict
from decimal import Decimal

class TestCategory(Enum):
    BASIC = "Basic Order Flows"
    MODS = "Modifications"
    CART = "Cart Management"
    PAYMENT = "Payment Flow"
    NATURAL = "Natural Language"
    ERROR = "Error Recovery"
    SESSION = "Session Management"

@dataclass
class TestCase:
    id: str
    category: TestCategory
    description: str
    messages: List[str]
    expected_states: List[str]
    expected_cart: Dict

class TestScenarios:
    def __init__(self):
        self.test_cases = [
            TestCase(
                id="BASIC-1",
                category=TestCategory.BASIC,
                description="Simple latte order",
                messages=[
                    "start",
                    "1",  # Order latte
                    "no",  # No modifications
                    "done",
                    "cash"
                ],
                expected_states=["INITIAL", "ORDERING", "MENU", "PAYMENT", "COMPLETED"],
                expected_cart={
                    "items": [{"name": "latte", "quantity": 1, "price": 3.50}],
                    "total": Decimal('3.50')
                }
            ),
            
            TestCase(
                id="CART-1",
                category=TestCategory.CART,
                description="Multiple items with modifier",
                messages=[
                    "start",
                    "Iced latte with almond milk and a muffin",
                    "yes",  # Confirm almond milk
                    "done",
                    "cash"
                ],
                expected_states=[
                    "INITIAL",
                    "ORDERING",
                    "MENU",
                    "PAYMENT",
                    "COMPLETED"
                ],
                expected_cart={
                    "items": [
                        {
                            "name": "Iced Latte",
                            "quantity": 1,
                            "price": 4.50,
                            "modifiers": ["almond milk"]
                        },
                        {
                            "name": "Muffin",
                            "quantity": 1,
                            "price": 3.00
                        }
                    ],
                    "total": Decimal('8.25')  # 4.50 + 0.75 + 3.00
                }
            ),
            
            TestCase(
                id="CART-2",
                category=TestCategory.CART,
                description="Sequential item addition",
                messages=[
                    "start",
                    "latte",
                    "no",  # No modifications for latte
                    "latte with almond milk",
                    "yes",  # Confirm almond milk
                    "done",
                    "cash"
                ],
                expected_states=[
                    "INITIAL",
                    "ORDERING",
                    "MENU",
                    "ORDERING",
                    "MENU",
                    "PAYMENT",
                    "COMPLETED"
                ],
                expected_cart={
                    "items": [
                        {
                            "name": "latte",
                            "quantity": 1,
                            "price": 3.50
                        },
                        {
                            "name": "Latte",
                            "quantity": 1,
                            "price": 4.50,
                            "modifiers": ["almond milk"]
                        }
                    ],
                    "total": Decimal('8.75')  # 3.50 + 4.50 + 0.75
                }
            )
        ]