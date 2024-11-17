from enum import Enum
from dataclasses import dataclass
from typing import List, Dict

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
                description="Simple espresso order",
                messages=[
                    "start",
                    "1",  # Order espresso
                    "done",
                    "4242-4242-4242-4242",
                    "confirm"
                ],
                expected_states=["INITIAL", "ORDERING", "PAYMENT", "PAYMENT", "COMPLETED"],
                expected_cart={"items": ["Espresso"], "total": 3.50}
            ),
            # Add more test cases here
        ] 