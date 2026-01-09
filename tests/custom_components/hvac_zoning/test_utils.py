"""Test utils."""

import pytest

from homeassistant.components.hvac_zoning.utils import (
    filter_to_valid_areas,
    get_all_thermostat_entity_ids,
)


@pytest.mark.parametrize(
    ("config_entry_data", "expected_config_entry_data"),
    [
        (
            {
                "areas": {
                    "basement": {
                        "covers": [],
                        "temperature": "sensor.basement_temperature",
                        "bedroom": False,
                    },
                    "office": {
                        "covers": ["cover.office_vent"],
                        "temperature": "sensor.office_temperature",
                        "bedroom": False,
                    },
                },
                "bed_time": "21:00:00",
                "wake_time": "05:00:00",
            },
            {
                "areas": {
                    "office": {
                        "covers": ["cover.office_vent"],
                        "temperature": "sensor.office_temperature",
                        "bedroom": False,
                    },
                },
                "bed_time": "21:00:00",
                "wake_time": "05:00:00",
            },
        ),
    ],
)
def test_filter_to_valid_areas(config_entry_data, expected_config_entry_data) -> None:
    """Test filter to valid areas."""
    actual_config_entry_data = filter_to_valid_areas(config_entry_data)

    assert actual_config_entry_data == expected_config_entry_data


@pytest.mark.parametrize(
    ("config_entry_data", "expected_thermostats"),
    [
        (
            {"areas": {"main_floor": {"climate": "climate.living_room_thermostat"}}},
            ["climate.living_room_thermostat"],
        ),
        (
            {
                "areas": {
                    "main_floor": {
                        "climate": "climate.living_room_thermostat",
                    },
                    "garage": {
                        "climate": "climate.garage_thermostat",
                    },
                }
            },
            ["climate.living_room_thermostat", "climate.garage_thermostat"],
        ),
    ],
)
def test_get_all_thermostat_entity_ids(config_entry_data, expected_thermostats) -> None:
    """Test get thermostat entity ids."""
    thermostats = get_all_thermostat_entity_ids(config_entry_data)

    assert thermostats == expected_thermostats
