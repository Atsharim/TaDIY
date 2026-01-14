"""Timeline visualization for schedule editor."""

from __future__ import annotations

from typing import Any


def get_temperature_color(temperature: float | str) -> str:
    """Get color for temperature value."""
    if isinstance(temperature, str):
        if temperature.lower() == "off":
            return "#6c757d"  # Gray for OFF
        return "#6c757d"

    # Color gradient from blue (cold) to red (warm)
    if temperature <= 15:
        return "#0d6efd"  # Blue
    elif temperature <= 18:
        return "#0dcaf0"  # Cyan
    elif temperature <= 20:
        return "#20c997"  # Teal
    elif temperature <= 22:
        return "#fd7e14"  # Orange
    else:
        return "#dc3545"  # Red


def format_temperature(temperature: float | str) -> str:
    """Format temperature for display."""
    if isinstance(temperature, str):
        if temperature.lower() == "off":
            return "OFF"
        return temperature
    return f"{temperature:.1f}°C"


def generate_timeline_html(blocks: list[dict[str, Any]]) -> str:
    """
    Generate HTML timeline visualization with colored blocks.

    Args:
        blocks: List of block dicts with start_time, end_time, temperature

    Returns:
        HTML string for timeline
    """
    if not blocks:
        return "<div style='padding: 10px; color: #999;'>No blocks defined</div>"

    # Sort blocks by start time
    sorted_blocks = sorted(blocks, key=lambda b: b["start_time"])

    # Calculate total duration (24 hours = 1440 minutes)
    total_minutes = 24 * 60

    # Build timeline HTML
    html = '<div style="margin: 20px 0;">'
    html += '<div style="display: flex; width: 100%; height: 60px; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">'

    for block in sorted_blocks:
        # Parse times - handle both HH:MM and H:MM formats
        start_time_str = block["start_time"]
        end_time_str = block["end_time"]

        # Split and handle variable length
        start_parts = start_time_str.split(":")
        end_parts = end_time_str.split(":")

        start_h = int(start_parts[0])
        start_m = int(start_parts[1]) if len(start_parts) > 1 else 0
        end_h = int(end_parts[0])
        end_m = int(end_parts[1]) if len(end_parts) > 1 else 0

        # Handle 23:59 as end-of-day (treat as 24:00 for calculations)
        if end_h == 23 and end_m == 59:
            end_total = 24 * 60
            display_end = "23:59"
        else:
            end_total = end_h * 60 + end_m
            display_end = end_time_str

        start_total = start_h * 60 + start_m

        # Calculate duration and percentage
        if end_total < start_total:
            # Wraps around midnight
            duration = (24 * 60) - start_total + end_total
        else:
            duration = end_total - start_total

        percentage = (duration / total_minutes) * 100

        # Get color
        color = get_temperature_color(block["temperature"])
        temp_display = format_temperature(block["temperature"])

        # Create block
        html += (
            f'<div style="flex: 0 0 {percentage:.2f}%; background: {color}; '
            'display: flex; align-items: center; justify-content: center; '
            'color: white; font-weight: bold; font-size: 12px; '
            'border-right: 1px solid rgba(255,255,255,0.3);">'
        )
        html += f'<div style="text-align: center; padding: 5px;">'
        html += f'<div style="font-size: 14px;">{temp_display}</div>'
        html += f'<div style="font-size: 10px; opacity: 0.9;">{start_time_str}-{display_end}</div>'
        html += '</div>'
        html += '</div>'

    html += '</div>'

    # Add time labels below
    html += '<div style="display: flex; justify-content: space-between; margin-top: 5px; font-size: 11px; color: #666;">'
    html += '<span>00:00</span>'
    html += '<span>06:00</span>'
    html += '<span>12:00</span>'
    html += '<span>18:00</span>'
    html += '<span>23:59</span>'
    html += '</div>'

    html += '</div>'

    return html


def generate_color_legend() -> str:
    """Generate color legend for temperature ranges."""
    html = '<div style="margin: 15px 0; padding: 10px; background: #f8f9fa; border-radius: 6px;">'
    html += '<div style="font-weight: bold; margin-bottom: 8px; font-size: 12px;">Color Coding:</div>'
    html += '<div style="display: flex; flex-wrap: wrap; gap: 10px; font-size: 11px;">'

    legend_items = [
        ("≤15°C", "#0d6efd"),
        ("16-18°C", "#0dcaf0"),
        ("19-20°C", "#20c997"),
        ("21-22°C", "#fd7e14"),
        (">22°C", "#dc3545"),
        ("OFF", "#6c757d"),
    ]

    for label, color in legend_items:
        html += '<div style="display: flex; align-items: center;">'
        html += f'<div style="width: 16px; height: 16px; background: {color}; border-radius: 3px; margin-right: 5px;"></div>'
        html += f'<span>{label}</span>'
        html += '</div>'

    html += '</div>'
    html += '</div>'

    return html
