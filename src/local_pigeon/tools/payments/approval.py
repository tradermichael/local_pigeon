"""
Payment Approval Handler

Manages the human-in-the-loop approval workflow for payments
above the configured threshold.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Awaitable


@dataclass
class ApprovalRequest:
    """A pending approval request."""
    
    id: str
    user_id: str
    platform: str
    tool_name: str
    action: str
    amount: float
    recipient: str
    description: str
    created_at: datetime
    expires_at: datetime
    status: str = "pending"  # pending, approved, denied, expired
    
    def to_message(self) -> str:
        """Format as a user-facing message."""
        return f"""🔐 Payment Approval Required

Tool: {self.tool_name}
Action: {self.action}
Amount: ${self.amount:.2f}
Recipient: {self.recipient}
Description: {self.description or 'N/A'}

Request ID: {self.id[:8]}
Expires: {self.expires_at.strftime('%H:%M:%S')}

Reply with:
  ✅ "approve" or "yes" to authorize
  ❌ "deny" or "no" to reject"""


class ApprovalManager:
    """
    Manages payment approval requests across platforms.
    
    Handles:
    - Creating approval requests
    - Storing pending approvals
    - Timeout handling
    - Platform-specific notification
    """
    
    def __init__(self, timeout_seconds: int = 300):
        self.timeout = timeout_seconds
        self._pending: dict[str, ApprovalRequest] = {}
        self._handlers: dict[str, Callable[[ApprovalRequest], Awaitable[None]]] = {}
        self._responses: dict[str, asyncio.Future] = {}
    
    def register_handler(
        self,
        platform: str,
        handler: Callable[[ApprovalRequest], Awaitable[None]],
    ) -> None:
        """
        Register a platform-specific notification handler.
        
        The handler should send the approval request to the user
        via their platform (Discord, Telegram, Web UI, etc.)
        """
        self._handlers[platform] = handler
    
    async def request_approval(
        self,
        user_id: str,
        platform: str,
        tool_name: str,
        action: str,
        amount: float,
        recipient: str,
        description: str = "",
    ) -> tuple[bool, str]:
        """
        Request approval from a user.
        
        Args:
            user_id: The user's identifier
            platform: Platform to send notification (discord, telegram, web)
            tool_name: Name of the tool requesting approval
            action: The action being performed
            amount: Payment amount in USD
            recipient: Payment recipient
            description: Optional description
            
        Returns:
            Tuple of (approved: bool, message: str)
        """
        import uuid
        from datetime import timedelta
        
        # Create approval request
        request_id = str(uuid.uuid4())
        now = datetime.now()
        
        request = ApprovalRequest(
            id=request_id,
            user_id=user_id,
            platform=platform,
            tool_name=tool_name,
            action=action,
            amount=amount,
            recipient=recipient,
            description=description,
            created_at=now,
            expires_at=now + timedelta(seconds=self.timeout),
        )
        
        self._pending[request_id] = request
        
        # Create response future
        response_future: asyncio.Future[bool] = asyncio.Future()
        self._responses[request_id] = response_future
        
        # Send notification via platform handler
        handler = self._handlers.get(platform)
        if handler:
            await handler(request)
        else:
            # No handler, auto-deny for safety
            self._cleanup(request_id)
            return False, "No approval handler configured for this platform."
        
        # Wait for response or timeout
        try:
            approved = await asyncio.wait_for(
                response_future,
                timeout=self.timeout,
            )
            
            if approved:
                request.status = "approved"
                message = f"✅ Payment of ${amount:.2f} approved."
            else:
                request.status = "denied"
                message = f"❌ Payment of ${amount:.2f} denied by user."
            
        except asyncio.TimeoutError:
            request.status = "expired"
            approved = False
            message = f"⏰ Approval request expired after {self.timeout} seconds."
        
        finally:
            self._cleanup(request_id)
        
        return approved, message
    
    def respond(self, request_id: str, approved: bool) -> bool:
        """
        Respond to an approval request.
        
        Args:
            request_id: The approval request ID (can be partial match)
            approved: True to approve, False to deny
            
        Returns:
            True if the request was found and responded to
        """
        # Allow partial ID matching
        full_id = None
        for rid in self._pending.keys():
            if rid.startswith(request_id) or request_id in rid:
                full_id = rid
                break
        
        if not full_id:
            return False
        
        future = self._responses.get(full_id)
        if future and not future.done():
            future.set_result(approved)
            return True
        
        return False
    
    def respond_for_user(self, user_id: str, approved: bool) -> bool:
        """
        Respond to the most recent pending approval for a user.
        
        Args:
            user_id: The user's identifier
            approved: True to approve, False to deny
            
        Returns:
            True if a pending request was found and responded to
        """
        # Find most recent pending request for user
        for request in sorted(
            self._pending.values(),
            key=lambda r: r.created_at,
            reverse=True,
        ):
            if request.user_id == user_id and request.status == "pending":
                return self.respond(request.id, approved)
        
        return False
    
    def get_pending(self, user_id: str) -> list[ApprovalRequest]:
        """Get all pending approvals for a user."""
        return [
            r for r in self._pending.values()
            if r.user_id == user_id and r.status == "pending"
        ]
    
    def _cleanup(self, request_id: str) -> None:
        """Clean up a completed request."""
        if request_id in self._responses:
            del self._responses[request_id]
        # Keep in pending for history (could add TTL cleanup)
    
    def clear_expired(self) -> int:
        """Clear expired requests. Returns count of cleared."""
        now = datetime.now()
        expired = [
            rid for rid, req in self._pending.items()
            if req.expires_at < now and req.status == "pending"
        ]
        
        for rid in expired:
            req = self._pending[rid]
            req.status = "expired"
            
            future = self._responses.get(rid)
            if future and not future.done():
                future.set_result(False)
            
            self._cleanup(rid)
        
        return len(expired)


# Global approval manager instance
_approval_manager: ApprovalManager | None = None


def get_approval_manager(timeout: int = 300) -> ApprovalManager:
    """Get or create the global approval manager."""
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ApprovalManager(timeout)
    return _approval_manager
