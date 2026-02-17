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
        from homeassistant.const import CONF_ENTITY_ID

        # Get room entity_id
        room_name = self.config_entry.data.get("room_name", "unknown")
        entity_id = f"climate.{room_name.lower().replace(' ', '_')}"

        # Create card config YAML
        card_yaml = f"""type: custom:tadiy-schedule-card
entity: {entity_id}"""

        # Show abort message with card config
        return self.async_abort(
            reason="use_lovelace_card",
            description_placeholders={
                "message": (
                    "Schedule editing uses a visual card interface.\n\n"
                    "═══════════════════════════════════════════════\n"
                    "QUICK SETUP:\n"
                    "═══════════════════════════════════════════════\n\n"
                    "1. Go to any Dashboard\n"
                    "2. Click '+ Add Card' → Manual Card\n"
                    "3. Paste this YAML:\n\n"
                    f"{card_yaml}\n\n"
                    "4. Click Save\n\n"
                    "The card will appear with a visual schedule editor!\n\n"
                    "═══════════════════════════════════════════════\n"
                    "FEATURES:\n"
                    "═══════════════════════════════════════════════\n"
                    "✓ Visual timeline with color-coded temperatures\n"
                    "✓ Real buttons for editing (not checkboxes!)\n"
                    "✓ Live validation with error messages\n"
                    "✓ Add/Edit/Delete schedule blocks\n"
                    "✓ Switch between modes (Normal, Homeoffice, etc.)\n\n"
                    "The card is automatically available at:\n"
                    "/tadiy/tadiy-schedule-card.js"
                )
            }
        )
