"""
Outreach Package for ShopeeStore.

This package orchestrates proactive outbound communication with qualified leads (store owners and
manufacturers). It encapsulates all channel-specific logic (e.g., Shopee Chat)
and content generation (e.g., varying pitches to avoid spam detection) required to securely and
efficiently deliver our trend intelligence dossier to potential subscribers.
"""

from .shopee_chat import (
    generate_varied_shopee_pitch,
    send_lead_message,
    send_shopee_outreach_batch,
)

__all__ = [
    "send_lead_message",
    "send_shopee_outreach_batch",
    "generate_varied_shopee_pitch",
]
