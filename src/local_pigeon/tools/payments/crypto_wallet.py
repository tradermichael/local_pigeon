"""
Cryptocurrency Wallet Tool

Provides crypto wallet functionality using Coinbase CDP (AgentKit).
Supports USDC payments on Base network.
"""

from dataclasses import dataclass, field
from typing import Any

from local_pigeon.tools.registry import Tool


@dataclass
class CryptoWalletTool(Tool):
    """
    Cryptocurrency wallet tool using Coinbase CDP.
    
    Supports:
    - Checking wallet balance
    - Sending USDC payments
    - Viewing transaction history
    - Receiving funds
    
    Note: Requires Coinbase CDP API credentials for full functionality.
    This implementation provides the interface and simulation mode.
    """
    
    name: str = "crypto_wallet"
    description: str = """Manage cryptocurrency wallet for payments.
Actions:
- balance: Check wallet balance (USDC, ETH)
- send: Send USDC payment (requires approval above threshold)
- receive: Get wallet address for receiving funds
- transactions: View recent transactions"""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["balance", "send", "receive", "transactions"],
                "description": "The action to perform"
            },
            "amount": {
                "type": "number",
                "description": "Amount to send (for send action)"
            },
            "token": {
                "type": "string",
                "enum": ["USDC", "ETH"],
                "description": "Token to use (default: USDC)",
                "default": "USDC"
            },
            "to_address": {
                "type": "string",
                "description": "Recipient wallet address (for send action)"
            },
            "memo": {
                "type": "string",
                "description": "Transaction memo/note"
            }
        },
        "required": ["action"]
    })
    requires_approval: bool = True
    crypto_settings: Any = field(default=None, repr=False)
    approval_settings: Any = field(default=None, repr=False)
    
    def __post_init__(self):
        self._cdp_key = self.crypto_settings.cdp_api_key_name if self.crypto_settings else ""
        self._network = self.crypto_settings.network if self.crypto_settings else "base"
        self._threshold = self.approval_settings.threshold if self.approval_settings else 25.0
        
        # Simulated wallet state
        self._usdc_balance = 100.0
        self._eth_balance = 0.01
        self._wallet_address = "0x1234...abcd"  # Would be real address with CDP
        self._transactions: list[dict] = []
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Execute a wallet action."""
        action = kwargs.get("action", "")
        
        if not action:
            return "Error: No action specified. Use: balance, send, receive, or transactions"
        
        try:
            if action == "balance":
                return await self._get_balance()
            elif action == "send":
                amount = kwargs.get("amount", 0)
                to_address = kwargs.get("to_address", "")
                token = kwargs.get("token", "USDC")
                memo = kwargs.get("memo", "")
                
                if not amount or amount <= 0:
                    return "Error: Valid amount required"
                if not to_address:
                    return "Error: Recipient address required"
                
                return await self._send_payment(
                    user_id=user_id,
                    amount=amount,
                    to_address=to_address,
                    token=token,
                    memo=memo,
                )
            elif action == "receive":
                return await self._get_receive_address()
            elif action == "transactions":
                return await self._get_transactions()
            else:
                return f"Error: Unknown action '{action}'"
                
        except Exception as e:
            return f"Error with crypto wallet: {str(e)}"
    
    async def _get_balance(self) -> str:
        """Get wallet balances."""
        # Calculate USD value (simulated prices)
        eth_price = 2500  # Simulated ETH price
        eth_usd = self._eth_balance * eth_price
        total_usd = self._usdc_balance + eth_usd
        
        return f"""🪙 Crypto Wallet Balance

Network: {self._network.title()}
Address: {self._wallet_address}

Balances:
  USDC: ${self._usdc_balance:.2f}
  ETH: {self._eth_balance:.4f} (~${eth_usd:.2f})

Total Value: ~${total_usd:.2f}

Approval Threshold: ${self._threshold:.2f}
Note: Payments above ${self._threshold:.2f} require your approval."""
    
    async def _send_payment(
        self,
        user_id: str,
        amount: float,
        to_address: str,
        token: str,
        memo: str,
    ) -> str:
        """Send a crypto payment."""
        # Validate token
        if token not in ["USDC", "ETH"]:
            return f"Error: Unsupported token '{token}'. Use USDC or ETH."
        
        # Check balance
        if token == "USDC":
            if amount > self._usdc_balance:
                return f"❌ Payment denied. Insufficient USDC balance.\nAvailable: ${self._usdc_balance:.2f}"
            self._usdc_balance -= amount
        else:
            if amount > self._eth_balance:
                return f"❌ Payment denied. Insufficient ETH balance.\nAvailable: {self._eth_balance:.4f} ETH"
            self._eth_balance -= amount
        
        # Validate address format (basic check)
        if not to_address.startswith("0x") or len(to_address) < 10:
            return "Error: Invalid wallet address format"
        
        # Process transaction (simulated)
        import datetime
        import secrets
        
        tx_hash = f"0x{secrets.token_hex(32)}"
        
        transaction = {
            "hash": tx_hash,
            "type": "send",
            "amount": amount,
            "token": token,
            "to": to_address,
            "memo": memo,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": "confirmed",
            "network": self._network,
        }
        self._transactions.append(transaction)
        
        # Format amount display
        if token == "USDC":
            amount_display = f"${amount:.2f} USDC"
        else:
            amount_display = f"{amount:.4f} ETH"
        
        return f"""✅ Transaction Successful

Amount: {amount_display}
To: {to_address[:10]}...{to_address[-6:]}
Network: {self._network.title()}
Memo: {memo or 'N/A'}

Transaction Hash: {tx_hash[:20]}...
Status: Confirmed

View on Explorer: https://basescan.org/tx/{tx_hash}"""
    
    async def _get_receive_address(self) -> str:
        """Get wallet address for receiving."""
        return f"""📥 Receive Crypto

Your Wallet Address:
{self._wallet_address}

Network: {self._network.title()}

Supported Tokens:
  • USDC (USD Coin)
  • ETH (Ethereum)

⚠️ Only send tokens on the {self._network.title()} network.
Tokens sent on other networks may be lost."""
    
    async def _get_transactions(self) -> str:
        """Get recent transactions."""
        if not self._transactions:
            return "No transactions yet."
        
        output = "🪙 Recent Transactions\n\n"
        
        for tx in reversed(self._transactions[-10:]):
            icon = "📤" if tx["type"] == "send" else "📥"
            
            if tx["token"] == "USDC":
                amount_str = f"${tx['amount']:.2f} USDC"
            else:
                amount_str = f"{tx['amount']:.4f} ETH"
            
            output += f"{icon} {tx['type'].title()}: {amount_str}\n"
            
            if tx["type"] == "send":
                output += f"   To: {tx['to'][:10]}...{tx['to'][-6:]}\n"
            
            output += f"   Date: {tx['timestamp'][:10]}\n"
            output += f"   Status: {tx['status']}\n"
            output += f"   Hash: {tx['hash'][:16]}...\n\n"
        
        return output
