"""Test Climate."""

from unittest.mock import AsyncMock

from homeassistant.components.climate.const import HVACMode
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, State

from custom_components.hvac_zoning.climate import Thermostat

name = "basement_thermostat"
temperature_sensor_entity_id = "sensor.basement_temperature"
thermostat_entity_id = "climate.living_room_thermostat"


def test_thermostat_default_target_temperature(hass: HomeAssistant) -> None:
    """Test thermostat default target temperature."""
    hass.states.async_set(thermostat_entity_id, HVACMode.HEAT)

    thermostat = Thermostat(
        hass, name, temperature_sensor_entity_id, thermostat_entity_id
    )

    assert thermostat._attr_target_temperature == 72.0
    assert thermostat.hvac_mode == HVACMode.HEAT


def test_thermostat_current_temperature_from_sensor(hass: HomeAssistant) -> None:
    """Test thermostat gets current temperature from temperature sensor."""
    hass.states.async_set(thermostat_entity_id, HVACMode.HEAT)
    hass.states.async_set(temperature_sensor_entity_id, "68.5")

    thermostat = Thermostat(
        hass, name, temperature_sensor_entity_id, thermostat_entity_id
    )

    assert thermostat.current_temperature == 68.5


def test_set_temperature(hass: HomeAssistant) -> None:
    """Test set temperature."""
    hass.states.async_set(thermostat_entity_id, HVACMode.HEAT)

    thermostat = Thermostat(
        hass, name, temperature_sensor_entity_id, thermostat_entity_id
    )

    target_temperature = 75.0
    kwargs = {ATTR_TEMPERATURE: target_temperature}
    thermostat.set_temperature(**kwargs)

    assert thermostat._attr_target_temperature == target_temperature


def test_current_temperature_updates_with_sensor_state(hass: HomeAssistant) -> None:
    """Test current temperature updates when sensor state changes."""
    hass.states.async_set(thermostat_entity_id, HVACMode.HEAT)
    hass.states.async_set(temperature_sensor_entity_id, "68.0")

    thermostat = Thermostat(
        hass, name, temperature_sensor_entity_id, thermostat_entity_id
    )

    assert thermostat.current_temperature == 68.0

    hass.states.async_set(temperature_sensor_entity_id, "69.0")

    assert thermostat.current_temperature == 69.0


def test_hvac_mode_updates_with_thermostat_state(hass: HomeAssistant) -> None:
    """Test hvac mode updates when central thermostat state changes."""
    hass.states.async_set(thermostat_entity_id, HVACMode.HEAT)

    thermostat = Thermostat(
        hass, name, temperature_sensor_entity_id, thermostat_entity_id
    )

    assert thermostat.hvac_mode == HVACMode.HEAT

    hass.states.async_set(thermostat_entity_id, HVACMode.COOL)

    assert thermostat.hvac_mode == HVACMode.COOL


def test_thermostat_with_unavailable_entities(hass: HomeAssistant) -> None:
    """Test thermostat when central thermostat and temperature sensor are not yet available."""
    thermostat = Thermostat(
        hass, name, temperature_sensor_entity_id, thermostat_entity_id
    )

    assert thermostat._attr_target_temperature == 72.0
    assert thermostat.current_temperature is None
    assert thermostat.hvac_mode is None


async def test_thermostat_restores_target_temperature(hass: HomeAssistant) -> None:
    """Test thermostat restores target temperature from previous state on restart."""
    previous_target_temp = 68.0

    thermostat = Thermostat(
        hass, name, temperature_sensor_entity_id, thermostat_entity_id
    )

    mock_state = State(
        f"climate.{name}",
        HVACMode.HEAT,
        {ATTR_TEMPERATURE: previous_target_temp},
    )
    thermostat.async_get_last_state = AsyncMock(return_value=mock_state)

    await thermostat._async_restore_target_temperature()

    assert thermostat._attr_target_temperature == previous_target_temp


async def test_thermostat_uses_default_when_no_previous_state(
    hass: HomeAssistant,
) -> None:
    """Test thermostat uses default target temperature when no previous state exists."""
    thermostat = Thermostat(
        hass, name, temperature_sensor_entity_id, thermostat_entity_id
    )

    thermostat.async_get_last_state = AsyncMock(return_value=None)

    await thermostat._async_restore_target_temperature()

    assert thermostat._attr_target_temperature == 72.0


async def test_thermostat_uses_default_when_previous_state_has_no_temperature(
    hass: HomeAssistant,
) -> None:
    """Test thermostat uses default when previous state has no temperature attribute."""
    thermostat = Thermostat(
        hass, name, temperature_sensor_entity_id, thermostat_entity_id
    )

    mock_state = State(
        f"climate.{name}",
        HVACMode.HEAT,
        {},
    )
    thermostat.async_get_last_state = AsyncMock(return_value=mock_state)

    await thermostat._async_restore_target_temperature()

    assert thermostat._attr_target_temperature == 72.0


async def test_thermostat_updates_when_temperature_sensor_comes_online(
    hass: HomeAssistant,
) -> None:
    """Test thermostat updates when temperature sensor transitions from unavailable to valid."""
    hass.states.async_set(thermostat_entity_id, HVACMode.HEAT)

    thermostat = Thermostat(
        hass, name, temperature_sensor_entity_id, thermostat_entity_id
    )
    thermostat.async_get_last_state = AsyncMock(return_value=None)
    thermostat.async_write_ha_state = AsyncMock()

    await thermostat.async_added_to_hass()

    assert thermostat.current_temperature is None

    hass.states.async_set(temperature_sensor_entity_id, "72.5")
    await hass.async_block_till_done()

    assert thermostat.current_temperature == 72.5
    thermostat.async_write_ha_state.assert_called()


async def test_thermostat_updates_when_temperature_sensor_transitions_from_unknown(
    hass: HomeAssistant,
) -> None:
    """Test thermostat updates when temperature sensor transitions from unknown to valid."""
    hass.states.async_set(thermostat_entity_id, HVACMode.HEAT)
    hass.states.async_set(temperature_sensor_entity_id, "unknown")

    thermostat = Thermostat(
        hass, name, temperature_sensor_entity_id, thermostat_entity_id
    )
    thermostat.async_get_last_state = AsyncMock(return_value=None)
    thermostat.async_write_ha_state = AsyncMock()

    await thermostat.async_added_to_hass()

    assert thermostat.current_temperature is None

    hass.states.async_set(temperature_sensor_entity_id, "68.0")
    await hass.async_block_till_done()

    assert thermostat.current_temperature == 68.0
    thermostat.async_write_ha_state.assert_called()


async def test_thermostat_does_not_update_on_valid_to_valid_temperature_change(
    hass: HomeAssistant,
) -> None:
    """Test thermostat does not call async_write_ha_state on valid to valid temp change."""
    hass.states.async_set(thermostat_entity_id, HVACMode.HEAT)
    hass.states.async_set(temperature_sensor_entity_id, "68.0")

    thermostat = Thermostat(
        hass, name, temperature_sensor_entity_id, thermostat_entity_id
    )
    thermostat.async_get_last_state = AsyncMock(return_value=None)
    thermostat.async_write_ha_state = AsyncMock()

    await thermostat.async_added_to_hass()

    thermostat.async_write_ha_state.reset_mock()

    hass.states.async_set(temperature_sensor_entity_id, "69.0")
    await hass.async_block_till_done()

    thermostat.async_write_ha_state.assert_not_called()
