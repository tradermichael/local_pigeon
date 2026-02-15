"""
Stripe Virtual Card Tool

Provides virtual card functionality using Stripe Issuing.
Includes spending controls and transaction tracking.
"""

from dataclasses import dataclass, field
from typing import Any

from local_pigeon.tools.registry import Tool


@dataclass
class StripeCardTool(Tool):
    """
    Stripe Issuing virtual card tool.
    
    Supports:
    - Creating virtual cards with spending limits
    - Making payments (simulated for now, real integration requires Stripe Issuing)
    - Checking card balance/limits
    - Viewing transaction history
    
    Note: Full Stripe Issuing requires business verification.
    This implementation provides the interface and can be connected
    to a real Stripe account when available.
    """
    
    name: str = "stripe_card"
    description: str = """Manage virtual debit cards and make payments.
Actions:
- balance: Check available balance and limits
- pay: Make a payment (requires approval above threshold)
- transactions: View recent transactions
- create_card: Create a new virtual card"""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["balance", "pay", "transactions", "create_card"],
                "description": "The action to perform"
            },
            "amount": {
                "type": "number",
                "description": "Payment amount in USD (for pay action)"
            },
            "recipient": {
                "type": "string",
                "description": "Payment recipient/merchant (for pay action)"
            },
            "description": {
                "type": "string",
                "description": "Payment description (for pay action)"
            },
            "card_id": {
                "type": "string",
                "description": "Card ID (optional, uses default if not specified)"
            },
            "spending_limit": {
                "type": "number",
                "description": "Monthly spending limit (for create_card action)"
            }
        },
        "required": ["action"]
    })
    requires_approval: bool = True
    stripe_settings: Any = field(default=None, repr=False)
    approval_settings: Any = field(default=None, repr=False)
    
    def __post_init__(self):
        self._api_key = self.stripe_settings.api_key if self.stripe_settings else ""
        self._threshold = self.approval_settings.threshold if self.approval_settings else 25.0
        self._daily_limit = self.approval_settings.daily_limit if self.approval_settings else 100.0
        
        # In-memory tracking (would be replaced with real Stripe API)
        self._transactions: list[dict] = []
        self._balance = 500.0  # Simulated balance
        self._daily_spent = 0.0
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Execute a card action."""
        action = kwargs.get("action", "")
        
        if not action:
            return "Error: No action specified. Use: balance, pay, transactions, or create_card"
        
        try:
            if action == "balance":
                return await self._get_balance()
            elif action == "pay":
                amount = kwargs.get("amount", 0)
                recipient = kwargs.get("recipient", "")
                description = kwargs.get("description", "")
                
                if not amount or amount <= 0:
                    return "Error: Valid payment amount required"
                if not recipient:
                    return "Error: Payment recipient required"
                
                return await self._make_payment(
                    user_id=user_id,
                    amount=amount,
                    recipient=recipient,
                    description=description,
                )
            elif action == "transactions":
                return await self._get_transactions()
            elif action == "create_card":
                spending_limit = kwargs.get("spending_limit", 500)
                return await self._create_card(spending_limit)
            else:
                return f"Error: Unknown action '{action}'"
                
        except Exception as e:
            return f"Error with Stripe card: {str(e)}"
    
    async def _get_balance(self) -> str:
        """Get card balance and limits."""
        return f"""💳 Card Balance

Available Balance: ${self._balance:.2f}
Daily Limit: ${self._daily_limit:.2f}
Daily Spent: ${self._daily_spent:.2f}
Daily Remaining: ${max(0, self._daily_limit - self._daily_spent):.2f}
Approval Threshold: ${self._threshold:.2f}

Note: Payments above ${self._threshold:.2f} require your approval."""
    
    async def _make_payment(
        self,
        user_id: str,
        amount: float,
        recipient: str,
        description: str,
    ) -> str:
        """Make a payment."""
        # Check daily limit
        if self._daily_spent + amount > self._daily_limit:
            remaining = self._daily_limit - self._daily_spent
            return f"❌ Payment denied. Daily limit exceeded.\nRemaining today: ${remaining:.2f}"
        
        # Check balance
        if amount > self._balance:
            return f"❌ Payment denied. Insufficient balance.\nAvailable: ${self._balance:.2f}"
        
        # Check per-transaction limit
        per_tx_limit = self.stripe_settings.spending_limit_per_transaction if self.stripe_settings else 50.0
        if amount > per_tx_limit:
            return f"❌ Payment denied. Exceeds per-transaction limit of ${per_tx_limit:.2f}"
        
        # Process payment (simulated)
        self._balance -= amount
        self._daily_spent += amount
        
        import datetime
        transaction = {
            "id": f"tx_{len(self._transactions) + 1:04d}",
            "amount": amount,
            "recipient": recipient,
            "description": description,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": "completed",
        }
        self._transactions.append(transaction)
        
        return f"""✅ Payment Successful

Amount: ${amount:.2f}
Recipient: {recipient}
Description: {description or 'N/A'}
Transaction ID: {transaction['id']}
Remaining Balance: ${self._balance:.2f}"""
    
    async def _get_transactions(self) -> str:
        """Get recent transactions."""
        if not self._transactions:
            return "No transactions yet."
        
        output = "💳 Recent Transactions\n\n"
        
        # Show last 10 transactions
        for tx in reversed(self._transactions[-10:]):
            output += f"ID: {tx['id']}\n"
            output += f"  Amount: ${tx['amount']:.2f}\n"
            output += f"  To: {tx['recipient']}\n"
            output += f"  Date: {tx['timestamp'][:10]}\n"
            output += f"  Status: {tx['status']}\n\n"
        
        return output
    
    async def _create_card(self, spending_limit: float) -> str:
        """Create a new virtual card."""
        import secrets
        
        # Generate simulated card details
        card_number = f"4242 **** **** {secrets.randbelow(10000):04d}"
        card_id = f"card_{secrets.token_hex(8)}"
        
        return f"""✅ Virtual Card Created

Card ID: {card_id}
Card Number: {card_number}
Type: Virtual Debit Card
Spending Limit: ${spending_limit:.2f}/month
Status: Active

Note: This is a simulated card. Connect Stripe Issuing API for real cards.
To enable real payments, add your Stripe API key to .env:
STRIPE_API_KEY=sk_live_..."""
