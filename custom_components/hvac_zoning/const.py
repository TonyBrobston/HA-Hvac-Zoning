"""Constants for the HVAC Zoning integration."""
import logging

from homeassistant.components.climate import HVACMode

LOGGER = logging.getLogger(__package__)

DOMAIN = "hvac_zoning"

SUPPORTED_HVAC_MODES = [HVACMode.HEAT, HVACMode.COOL]

ACTIVE = "active"
IDLE = "idle"
