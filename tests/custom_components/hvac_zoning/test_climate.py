"""Test Climate."""

from homeassistant.components.climate.const import HVACMode
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant

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
