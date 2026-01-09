"""Test init."""

from unittest.mock import MagicMock, call

from freezegun import freeze_time
import pytest

from homeassistant import core
from homeassistant.components.climate import SERVICE_SET_TEMPERATURE, HVACMode
from homeassistant.components.hvac_zoning import (
    adjust_house,
    async_setup_entry,
    determine_action,
    determine_change_in_temperature,
    determine_cover_service_to_call,
    determine_if_night_time_mode,
    determine_is_night_time,
    filter_to_bedrooms,
    get_all_cover_entity_ids,
    get_all_temperature_entity_ids,
)
from homeassistant.components.hvac_zoning.const import ACTIVE, DOMAIN, IDLE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    EVENT_STATE_CHANGED,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    STATE_CLOSED,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def test_get_all_cover_entity_ids() -> None:
    """Test get all cover entities."""
    areas = {
        "basement": {
            "covers": [
                "cover.basement_west_vent",
                "cover.basement_northeast_vent",
                "cover.basement_southeast_vent",
            ],
            "temperature": "sensor.basement_temperature",
        },
        "upstairs_bathroom": {
            "covers": ["cover.upstairs_bathroom_vent"],
            "temperature": "sensor.upstairs_bathroom_temperature",
        },
    }

    entities = get_all_cover_entity_ids(areas)

    assert entities == [
        "cover.basement_west_vent",
        "cover.basement_northeast_vent",
        "cover.basement_southeast_vent",
        "cover.upstairs_bathroom_vent",
    ]


def test_get_all_temperature_entity_ids() -> None:
    """Test get all temperature entities."""
    areas = {
        "office": {
            "covers": ["cover.office_vent"],
            "temperature": "sensor.office_temperature",
        },
        "upstairs_bathroom": {
            "covers": ["cover.upstairs_bathroom_vent"],
            "temperature": "sensor.upstairs_bathroom_temperature",
        },
    }

    entities = get_all_temperature_entity_ids(areas)

    assert entities == [
        "sensor.office_temperature",
        "sensor.upstairs_bathroom_temperature",
    ]


@pytest.mark.parametrize(
    ("areas", "expected_result"),
    [
        ({"office": {"bedroom": True}}, True),
        ({"upstairs_bathroom": {"bedroom": False}}, False),
        ({"office": {"bedroom": True}, "upstairs_bathroom": {"bedroom": False}}, True),
        (
            {"office": {"bedroom": False}, "upstairs_bathroom": {"bedroom": False}},
            False,
        ),
        ({}, False),
    ],
)
def test_determine_if_night_time_mode(areas, expected_result) -> None:
    """Test determine if night time mode."""
    is_night_time_mode = determine_if_night_time_mode(areas)
    assert is_night_time_mode == expected_result


@pytest.mark.parametrize(
    ("target_temperature", "actual_temperature", "hvac_mode", "expected_action"),
    [
        (73, 71, HVACMode.HEAT, ACTIVE),
        (70, 71, HVACMode.COOL, ACTIVE),
        (73, "71.52", HVACMode.HEAT, ACTIVE),
        (70, "71.52", HVACMode.COOL, ACTIVE),
        ("73.1", 71, HVACMode.HEAT, ACTIVE),
        ("70.1", 71, HVACMode.COOL, ACTIVE),
        (71, 73, HVACMode.HEAT, IDLE),
        (71, 70, HVACMode.COOL, IDLE),
        ("71.52", 73, HVACMode.HEAT, IDLE),
        ("71.52", 70, HVACMode.COOL, IDLE),
        (71, "73.1", HVACMode.HEAT, IDLE),
        (71, "70.1", HVACMode.COOL, IDLE),
    ],
)
def test_determine_action(
    target_temperature, actual_temperature, hvac_mode, expected_action
) -> None:
    """Test determine action."""
    action = determine_action(target_temperature, actual_temperature, hvac_mode)
    assert action == expected_action


@pytest.mark.parametrize(
    (
        "target_temperature",
        "actual_temperature",
        "hvac_mode",
        "thermostat_action",
        "is_night_time_mode",
        "is_night_time",
        "is_bedroom",
        "control_central_thermostat",
        "expected_service",
    ),
    [
        (71, 70, HVACMode.HEAT, None, False, False, False, True, SERVICE_OPEN_COVER),
        (69, 70, HVACMode.HEAT, None, False, False, False, True, SERVICE_CLOSE_COVER),
        (70, 70, HVACMode.HEAT, None, False, False, False, True, SERVICE_CLOSE_COVER),
        (69, 70, HVACMode.COOL, None, False, False, False, True, SERVICE_OPEN_COVER),
        (71, 70, HVACMode.COOL, None, False, False, False, True, SERVICE_CLOSE_COVER),
        (71, 70, None, None, False, False, False, True, SERVICE_OPEN_COVER),
        (
            71,
            70,
            HVACMode.HEAT_COOL,
            None,
            False,
            False,
            False,
            True,
            SERVICE_OPEN_COVER,
        ),
        (None, 70, HVACMode.HEAT, None, False, False, False, True, SERVICE_OPEN_COVER),
        (70, None, HVACMode.HEAT, None, False, False, False, True, SERVICE_OPEN_COVER),
        (None, 70, HVACMode.COOL, None, False, False, False, True, SERVICE_OPEN_COVER),
        (70, None, HVACMode.COOL, None, False, False, False, True, SERVICE_OPEN_COVER),
        (70, 70, HVACMode.COOL, IDLE, False, False, False, True, SERVICE_OPEN_COVER),
        (70, 70, HVACMode.COOL, None, True, True, True, True, SERVICE_OPEN_COVER),
        (70, 70, HVACMode.COOL, None, True, True, False, True, SERVICE_CLOSE_COVER),
        (70, 70, HVACMode.COOL, None, True, False, False, True, SERVICE_CLOSE_COVER),
        (70, 70, HVACMode.COOL, None, False, False, False, True, SERVICE_CLOSE_COVER),
        (70, 70, HVACMode.COOL, None, False, True, False, True, SERVICE_CLOSE_COVER),
        (70, 70, HVACMode.COOL, None, False, True, True, True, SERVICE_CLOSE_COVER),
        (71, 70, HVACMode.COOL, IDLE, False, False, False, False, SERVICE_CLOSE_COVER),
    ],
)
def test_determine_cover_service_to_call(
    target_temperature,
    actual_temperature,
    hvac_mode,
    thermostat_action,
    is_night_time_mode,
    is_night_time,
    is_bedroom,
    control_central_thermostat,
    expected_service,
) -> None:
    """Test determine cover service."""
    service = determine_cover_service_to_call(
        target_temperature,
        actual_temperature,
        hvac_mode,
        thermostat_action,
        is_night_time_mode,
        is_night_time,
        is_bedroom,
        control_central_thermostat,
    )

    assert service == expected_service


@pytest.mark.parametrize(
    ("target_temperature", "hvac_mode", "action", "expected_change_in_temperature"),
    [
        (68, HVACMode.HEAT, ACTIVE, 70),
        (68, HVACMode.COOL, ACTIVE, 66),
        (68, HVACMode.OFF, ACTIVE, 68),
        (68, HVACMode.HEAT, IDLE, 68),
        (68, HVACMode.HEAT_COOL, ACTIVE, 68),
    ],
)
def test_determine_change_in_temperature(
    target_temperature, hvac_mode, action, expected_change_in_temperature
) -> None:
    """Test determine change in temperature."""
    change_in_temperature = determine_change_in_temperature(
        target_temperature, hvac_mode, action
    )
    assert change_in_temperature == expected_change_in_temperature


@pytest.mark.parametrize(
    ("test_date", "bed_time", "wake_time", "expected_result"),
    [
        ("2024-01-01 12:59:59", "21:00:00", "05:00:00", True),
        ("2024-01-01 05:00:01", "21:00:00", "05:00:00", True),
        ("2024-01-01 07:59:59", "21:00:00", "05:00:00", True),
        ("2024-01-01 13:00:00", "21:00:00", "05:00:00", False),
        ("2024-01-01 05:00:00", "21:00:00", "05:00:00", False),
        ("2024-01-01 20:00:00", "21:00:00", "05:00:00", False),
    ],
)
def test_determine_is_night_time(
    test_date, bed_time, wake_time, expected_result, hass: HomeAssistant
) -> None:
    """Test determine is night time."""
    with freeze_time(test_date):
        is_night_time = determine_is_night_time(bed_time, wake_time)

        assert is_night_time is expected_result


@pytest.mark.parametrize(
    ("areas", "expected_result"),
    [
        (
            {
                "office": {
                    "covers": ["cover.office_vent"],
                    "temperature": "sensor.office_temperature",
                    "bedroom": False,
                },
                "upstairs_bathroom": {
                    "covers": ["cover.upstairs_bathroom_vent"],
                    "temperature": "sensor.upstairs_bathroom_temperature",
                    "bedroom": True,
                },
            },
            {
                "upstairs_bathroom": {
                    "covers": ["cover.upstairs_bathroom_vent"],
                    "temperature": "sensor.upstairs_bathroom_temperature",
                    "bedroom": True,
                },
            },
        ),
        ({}, {}),
    ],
)
def test_filter_to_bedrooms(areas, expected_result) -> None:
    """Test filter to bedrooms."""
    assert filter_to_bedrooms(areas) == expected_result


central_thermostat_entity_id = "climate.living_room_thermostat"
cover_entity_id = "cover.master_bedroom_vent"
cover_connectivity_entity_id = "binary_sensor.status"
area_target_temperature_entity_id = "climate.master_bedroom_thermostat"
area_actual_temperature_entity_id = "sensor.master_bedroom_temperature"
data = {
    "areas": {
        "master_bedroom": {
            "covers": [cover_entity_id],
            "connectivities": [cover_connectivity_entity_id],
            "temperature": area_actual_temperature_entity_id,
            "bedroom": False,
        },
        "main_floor": {
            "climate": central_thermostat_entity_id,
            "bedroom": False,
        },
    },
    "bed_time": "21:00:00",
    "wake_time": "05:00:00",
    "control_central_thermostat": True,
}


async def test_adjust_house(hass: HomeAssistant) -> None:
    """Test adjust house."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
    )
    hass.states.async_set(
        entity_id=central_thermostat_entity_id,
        new_state="heat",
        attributes={
            "current_temperature": 68,
        },
    )
    hass.states.async_set(
        entity_id=cover_entity_id,
        new_state="open",
    )
    hass.states.async_set(
        entity_id=area_target_temperature_entity_id,
        new_state=None,
        attributes={
            "temperature": 71,
        },
    )
    hass.states.async_set(
        entity_id=area_actual_temperature_entity_id,
        new_state=70,
    )
    await hass.async_block_till_done()
    hass.services = MagicMock()

    adjust_house(hass, config_entry)

    hass.services.call.assert_has_calls(
        [
            call(
                Platform.COVER,
                SERVICE_OPEN_COVER,
                service_data={ATTR_ENTITY_ID: cover_entity_id},
            ),
            call(
                Platform.CLIMATE,
                SERVICE_SET_TEMPERATURE,
                service_data={
                    ATTR_ENTITY_ID: central_thermostat_entity_id,
                    ATTR_TEMPERATURE: 70,
                },
            ),
        ]
    )


async def test_adjust_house_control_central_thermostat_false(
    hass: HomeAssistant,
) -> None:
    """Test adjust house."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **data,
            "control_central_thermostat": False,
        },
    )
    hass.states.async_set(
        entity_id=central_thermostat_entity_id,
        new_state="heat",
        attributes={
            "current_temperature": 68,
        },
    )
    hass.states.async_set(
        entity_id=cover_entity_id,
        new_state="open",
    )
    hass.states.async_set(
        entity_id=area_target_temperature_entity_id,
        new_state=None,
        attributes={
            "temperature": 71,
        },
    )
    hass.states.async_set(
        entity_id=area_actual_temperature_entity_id,
        new_state=70,
    )
    await hass.async_block_till_done()
    hass.services = MagicMock()

    adjust_house(hass, config_entry)

    assert hass.services.call.call_count == 1
    hass.services.call.assert_has_calls(
        [
            call(
                Platform.COVER,
                SERVICE_OPEN_COVER,
                service_data={ATTR_ENTITY_ID: cover_entity_id},
            )
        ]
    )


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async setup entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        state=ConfigEntryState.LOADED,
    )
    hass.states.async_set(
        entity_id=central_thermostat_entity_id,
        new_state="heat",
        attributes={
            "current_temperature": 68,
        },
    )
    hass.states.async_set(
        entity_id=cover_entity_id,
        new_state="open",
    )
    hass.states.async_set(
        entity_id=area_target_temperature_entity_id,
        new_state=None,
        attributes={
            "temperature": 70,
        },
    )
    hass.states.async_set(
        entity_id=area_actual_temperature_entity_id,
        new_state=69,
    )
    await hass.async_block_till_done()
    hass.services = MagicMock()

    await async_setup_entry(hass, config_entry)

    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {
            ATTR_ENTITY_ID: area_target_temperature_entity_id,
            "old_state": core.State(
                area_target_temperature_entity_id,
                71,
            ),
        },
    )
    await hass.async_block_till_done()

    assert hass.services.call.call_count == 2
    hass.services.call.assert_has_calls(
        [
            call(
                Platform.COVER,
                SERVICE_OPEN_COVER,
                service_data={ATTR_ENTITY_ID: cover_entity_id},
            ),
            call(
                Platform.CLIMATE,
                SERVICE_SET_TEMPERATURE,
                service_data={
                    ATTR_ENTITY_ID: central_thermostat_entity_id,
                    ATTR_TEMPERATURE: 70,
                },
            ),
        ]
    )


async def test_async_setup_entry_damper_wake(hass: HomeAssistant) -> None:
    """Test async setup entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **data,
            "control_central_thermostat": False,
        },
        state=ConfigEntryState.LOADED,
    )
    hass.states.async_set(
        entity_id=central_thermostat_entity_id,
        new_state="heat",
        attributes={
            "current_temperature": 68,
        },
    )
    hass.states.async_set(
        entity_id=area_target_temperature_entity_id,
        new_state=None,
        attributes={
            "temperature": 70,
        },
    )
    hass.states.async_set(
        entity_id=area_actual_temperature_entity_id,
        new_state=69,
    )
    await hass.async_block_till_done()
    hass.services = MagicMock()

    await async_setup_entry(hass, config_entry)

    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {
            ATTR_ENTITY_ID: cover_connectivity_entity_id,
            "old_state": core.State(
                cover_entity_id,
                STATE_OFF,
            ),
            "new_state": core.State(
                cover_entity_id,
                STATE_ON,
            ),
        },
    )
    await hass.async_block_till_done()

    assert hass.services.call.call_count == 1
    hass.services.call.assert_has_calls(
        [
            call(
                Platform.COVER,
                SERVICE_OPEN_COVER,
                service_data={ATTR_ENTITY_ID: cover_entity_id},
            ),
        ]
    )


async def test_async_setup_entry_damper_open(hass: HomeAssistant) -> None:
    """Test async setup entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **data,
            "control_central_thermostat": False,
        },
        state=ConfigEntryState.LOADED,
    )
    hass.states.async_set(
        entity_id=central_thermostat_entity_id,
        new_state="heat",
        attributes={
            "current_temperature": 68,
        },
    )
    hass.states.async_set(
        entity_id=cover_entity_id,
        new_state="open",
    )
    hass.states.async_set(
        entity_id=area_target_temperature_entity_id,
        new_state=None,
        attributes={
            "temperature": 70,
        },
    )
    hass.states.async_set(
        entity_id=area_actual_temperature_entity_id,
        new_state=69,
    )
    await hass.async_block_till_done()
    hass.services = MagicMock()

    await async_setup_entry(hass, config_entry)

    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {
            ATTR_ENTITY_ID: cover_entity_id,
            "old_state": core.State(
                cover_entity_id,
                STATE_CLOSED,
            ),
        },
    )
    await hass.async_block_till_done()

    assert hass.services.call.call_count == 0
