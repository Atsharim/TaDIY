"""Schedule editor flow for TaDIY - Simplified to use Lovelace Card."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.data_entry_flow import FlowResult

_LOGGER = logging.getLogger(__name__)


class ScheduleEditorMixin:
    """Mixin for schedule editor functionality in options flow."""

    async def async_step_manage_schedules(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show information about using the Lovelace card for schedule editing."""
        # Just show an abort message with instructions
        return self.async_abort(
            reason="use_lovelace_card",
            description_placeholders={
                "message": (
                    "Schedule editing is now done via a custom Lovelace card.\n\n"
                    "═══════════════════════════════════\n"
                    "AUTOMATIC SETUP (Recommended):\n"
                    "═══════════════════════════════════\n\n"
                    "1. Go to your dashboard\n"
                    "2. Click '+ Add Card'\n"
                    "3. Search for 'TaDIY Schedule Card'\n"
                    "4. Configure the card:\n"
                    "   entity: climate.YOUR_ROOM_NAME\n\n"
                    "The card is automatically available at:\n"
                    "  /tadiy/tadiy-schedule-card.js\n\n"
                    "═══════════════════════════════════\n"
                    "FEATURES:\n"
                    "═══════════════════════════════════\n"
                    "✓ Interactive visual timeline\n"
                    "✓ Add/Edit/Delete blocks with real buttons\n"
                    "✓ Live validation and updates\n"
                    "✓ Color-coded temperature display\n"
                    "✓ Multiple mode support\n\n"
                    "═══════════════════════════════════\n"
                    "MANUAL REGISTRATION (Optional):\n"
                    "═══════════════════════════════════\n\n"
                    "If the card doesn't appear, add to configuration.yaml:\n\n"
                    "lovelace:\n"
                    "  resources:\n"
                    "    - url: /tadiy/tadiy-schedule-card.js\n"
                    "      type: module\n\n"
                    "Then restart Home Assistant."
                )
            }
        )
