"""
Financial tools for securely tracking and analyzing markets and budgets locally.
"""

import sqlite3
import json
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from local_pigeon.tools.registry import Tool
from local_pigeon.config import get_data_dir

logger = logging.getLogger(__name__)

class LocalLedgerTool(Tool):
    """
    Highly secure, local-only SQLite ledger for budgeting and CPA tasks.
    No data leaves the user's machine.
    """
    
    name = "local_ledger"
    description = (
        "Manage a private, local-only double-entry ledger for budgeting, "
        "tracking expenses, and CPA analysis. Use this to safely log transactions."
    )
    
    class Parameters(BaseModel):
        action: str = Field(description="Action to perform: 'add_entry', 'get_balance', or 'get_report'")
        account: str = Field(None, description="Account name (e.g. 'checking', 'groceries')")
        amount: float = Field(None, description="Amount (positive for credits, negative for debits)")
        description: str = Field(None, description="Description of the transaction")
        
    def __init__(self):
        super().__init__()
        self.db_path = get_data_dir() / "ledger.db"
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    account TEXT NOT NULL,
                    amount REAL NOT NULL,
                    description TEXT
                )
            ''')
            
    async def execute(self, action: str, account: str = None, amount: float = None, description: str = None) -> str:
        try:
            with sqlite3.connect(self.db_path) as conn:
                if action == "add_entry":
                    if not account or amount is None:
                        return "Error: 'account' and 'amount' required for add_entry"
                    conn.execute(
                        "INSERT INTO ledger (account, amount, description) VALUES (?, ?, ?)",
                        (account, amount, description)
                    )
                    return f"Successfully added {amount} to {account} local ledger."
                
                elif action == "get_balance":
                    if not account:
                        return "Error: 'account' required for get_balance"
                    cursor = conn.execute("SELECT SUM(amount) FROM ledger WHERE account=?", (account,))
                    balance = cursor.fetchone()[0] or 0.0
                    return f"Current balance for local account '{account}': {balance}"
                    
                elif action == "get_report":
                    cursor = conn.execute("SELECT account, SUM(amount) FROM ledger GROUP BY account")
                    report = {row[0]: row[1] for row in cursor.fetchall()}
                    return f"Privately generated local financial report: {json.dumps(report, indent=2)}"
                    
                else:
                    return f"Unknown action: {action}"
        except Exception as e:
            logger.error(f"Local ledger error: {e}")
            return f"Error executing ledger action: {str(e)}"
