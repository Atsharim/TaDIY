#!/bin/bash
# Clear Python cache for TaDIY integration
# Run this in Home Assistant after updating code

echo "Clearing TaDIY Python cache..."
find /config/custom_components/tadiy -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find /config/custom_components/tadiy -type f -name "*.pyc" -delete 2>/dev/null
find /config/custom_components/tadiy -type f -name "*.pyo" -delete 2>/dev/null

echo "Cache cleared! Now restart Home Assistant:"
echo "  ha core restart"
