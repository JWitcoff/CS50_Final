from enum import Enum

class OrderStage(Enum):
    MENU = "menu"
    MODIFICATIONS = "modifications"
    CHECKOUT = "checkout"
    PAYMENT = "payment"
    AWAITING_CARD = "awaiting_card"
    COMPLETED = "completed"