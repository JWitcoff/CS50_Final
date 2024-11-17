from enum import Enum

class OrderStage(Enum):
    INITIAL = "initial"
    DRINK_SELECTION = "drink_selection"
    MODIFICATIONS = "modifications"
    CONFIRMATION = "confirmation"
    CHECKOUT = "checkout"