"""Utils."""


def filter_to_valid_areas(config_entry_data):
    """Filter to valid areas."""
    areas = config_entry_data.get("areas", {})
    return {
        **config_entry_data,
        "areas": {
            key: value
            for key, value in areas.items()
            if "covers" in value and len(value["covers"]) > 0
        },
    }


def get_all_thermostat_entity_ids(config_entry_data):
    """Get thermostat entity ids."""
    return [
        area["climate"]
        for area in config_entry_data.get("areas", {}).values()
        if "climate" in area
    ]
