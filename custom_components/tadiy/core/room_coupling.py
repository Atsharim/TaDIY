"""Multi-room heat coupling for TaDIY.

Phase 3.2: Models heat transfer awareness between adjacent rooms.
When a neighboring room is actively heating, reduces the target temp
slightly to account for heat transfer through shared walls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Coupling constants
DEFAULT_COUPLING_REDUCTION = 0.5  # °C reduction when neighbor is heating
MAX_COUPLING_REDUCTION = 1.5  # Maximum temperature reduction from coupling
NEIGHBOR_HEATING_THRESHOLD = 0.5  # °C above target to be considered "actively heating"


@dataclass
class RoomCouplingState:
    """State of heat coupling for a room."""

    room_name: str
    adjacent_rooms: list[str] = field(default_factory=list)
    coupling_strength: float = 0.5  # 0.0 - 1.0
    neighbors_heating: list[str] = field(default_factory=list)
    coupling_adjustment: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "room_name": self.room_name,
            "adjacent_rooms": self.adjacent_rooms,
            "coupling_strength": self.coupling_strength,
            "neighbors_heating": self.neighbors_heating,
            "coupling_adjustment": self.coupling_adjustment,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomCouplingState:
        """Create from dictionary."""
        return cls(
            room_name=data["room_name"],
            adjacent_rooms=data.get("adjacent_rooms", []),
            coupling_strength=data.get("coupling_strength", 0.5),
            neighbors_heating=data.get("neighbors_heating", []),
            coupling_adjustment=data.get("coupling_adjustment", 0.0),
        )


class RoomCouplingManager:
    """
    Manages heat coupling between adjacent rooms.
    
    When adjacent rooms are actively heating, reduces the target temperature
    to account for heat transfer through shared walls, saving energy.
    """

    def __init__(self) -> None:
        """Initialize the coupling manager."""
        self._room_states: dict[str, RoomCouplingState] = {}

    def register_room(
        self,
        room_name: str,
        adjacent_rooms: list[str],
        coupling_strength: float = 0.5,
    ) -> None:
        """
        Register a room for coupling calculations.
        
        Args:
            room_name: Name of the room
            adjacent_rooms: List of adjacent room names
            coupling_strength: How much to adjust for coupling (0.0-1.0)
        """
        self._room_states[room_name] = RoomCouplingState(
            room_name=room_name,
            adjacent_rooms=adjacent_rooms,
            coupling_strength=coupling_strength,
        )
        _LOGGER.debug(
            "Registered room %s for coupling with neighbors: %s (strength: %.1f)",
            room_name,
            adjacent_rooms,
            coupling_strength,
        )

    def update_room_heating_status(
        self,
        room_name: str,
        is_heating: bool,
        current_temp: float | None = None,
        target_temp: float | None = None,
    ) -> None:
        """
        Update the heating status of a room.
        
        Called by room coordinators to report their current state.
        This information is used to determine if heat is flowing from neighbors.
        
        Args:
            room_name: Name of the room
            is_heating: Whether the room's heating system is active
            current_temp: Current temperature (optional, for delta calculation)
            target_temp: Target temperature (optional, for delta calculation)
        """
        # Check if this room is "actively heating" (significant temp delta)
        actively_heating = is_heating
        if current_temp is not None and target_temp is not None:
            delta = target_temp - current_temp
            actively_heating = delta > NEIGHBOR_HEATING_THRESHOLD

        # Update all rooms that have this room as a neighbor
        for state in self._room_states.values():
            if room_name in state.adjacent_rooms:
                if actively_heating and room_name not in state.neighbors_heating:
                    state.neighbors_heating.append(room_name)
                elif not actively_heating and room_name in state.neighbors_heating:
                    state.neighbors_heating.remove(room_name)

    def get_coupling_adjustment(self, room_name: str) -> float:
        """
        Get the temperature adjustment due to neighboring room heating.
        
        Args:
            room_name: Name of the room
            
        Returns:
            Temperature adjustment (negative value = reduce target)
        """
        state = self._room_states.get(room_name)
        if not state or not state.neighbors_heating:
            return 0.0

        # Calculate adjustment based on number of heating neighbors and strength
        neighbor_count = len(state.neighbors_heating)
        base_reduction = DEFAULT_COUPLING_REDUCTION * neighbor_count

        # Apply coupling strength
        adjusted_reduction = base_reduction * state.coupling_strength

        # Cap at maximum
        final_reduction = min(adjusted_reduction, MAX_COUPLING_REDUCTION)

        # Store for diagnostics
        state.coupling_adjustment = -final_reduction

        if final_reduction > 0:
            _LOGGER.debug(
                "Room %s: Coupling adjustment: -%.1f°C (neighbors heating: %s)",
                room_name,
                final_reduction,
                state.neighbors_heating,
            )

        return -final_reduction  # Negative = reduce target

    def get_room_state(self, room_name: str) -> RoomCouplingState | None:
        """Get current coupling state for a room."""
        return self._room_states.get(room_name)

    def get_all_states(self) -> dict[str, RoomCouplingState]:
        """Get all room coupling states."""
        return self._room_states.copy()

    def unregister_room(self, room_name: str) -> None:
        """Remove a room from coupling calculations."""
        if room_name in self._room_states:
            del self._room_states[room_name]

        # Also remove from neighbors lists
        for state in self._room_states.values():
            if room_name in state.adjacent_rooms:
                state.adjacent_rooms.remove(room_name)
            if room_name in state.neighbors_heating:
                state.neighbors_heating.remove(room_name)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "room_states": {
                name: state.to_dict() for name, state in self._room_states.items()
            }
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomCouplingManager:
        """Create from dictionary."""
        manager = cls()
        for name, state_data in data.get("room_states", {}).items():
            manager._room_states[name] = RoomCouplingState.from_dict(state_data)
        return manager
