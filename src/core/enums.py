from enum import Enum

class OrderStage(Enum):
    MENU = "menu"
    MODIFICATIONS = "modifications"
    CHECKOUT = "checkout"
    PAYMENT = "payment"
    AWAITING_CARD = "awaiting_card"
    COMPLETED = "completed"
    AWAITING_MOD_CONFIRM = "awaiting_mod_confirm"
    AWAITING_PAYMENT_CONFIRM = "awaiting_payment_confirm"
    AWAITING_PAYMENT_METHOD = "awaiting_payment_method"
    AWAITING_PAYMENT_AMOUNT = "awaiting_payment_amount"
    AWAITING_PAYMENT_CONFIRMATION = "awaiting_payment_confirmation"
    AWAITING_PAYMENT_RECEIPT = "awaiting_payment_receipt"
    AWAITING_PAYMENT_RECEIPT_CONFIRMATION = "awaiting_payment_receipt_confirmation"
