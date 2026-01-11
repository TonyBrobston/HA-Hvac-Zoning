"""Utils."""

from .const import LOGGER


def filter_to_valid_areas(config_entry_data):
    """Filter to valid areas."""
    areas = config_entry_data.get("areas", {})
    LOGGER.info("hvac_zoning: filter_to_valid_areas: input areas=%s", list(areas.keys()))
    valid_areas = {
        key: value
        for key, value in areas.items()
        if "covers" in value and len(value["covers"]) > 0
    }
    invalid_areas = [key for key in areas.keys() if key not in valid_areas]
    if invalid_areas:
        LOGGER.info(
            "filter_to_valid_areas: filtered out areas=%s (no covers configured)",
            invalid_areas,
        )
    LOGGER.info("hvac_zoning: filter_to_valid_areas: valid areas=%s", list(valid_areas.keys()))
    return {
        **config_entry_data,
        "areas": valid_areas,
    }


def get_all_thermostat_entity_ids(config_entry_data):
    """Get thermostat entity ids."""
    LOGGER.info("hvac_zoning: get_all_thermostat_entity_ids: config_entry_data areas=%s", list(config_entry_data.get("areas", {}).keys()))
    thermostat_ids = [
        area["climate"]
        for area in config_entry_data.get("areas", {}).values()
        if "climate" in area
    ]
    LOGGER.info("hvac_zoning: get_all_thermostat_entity_ids: found thermostat_ids=%s", thermostat_ids)
    return thermostat_ids
