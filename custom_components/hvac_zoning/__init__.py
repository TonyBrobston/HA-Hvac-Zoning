"""The HVAC Zoning integration."""

from __future__ import annotations

import datetime

from homeassistant.components.climate import SERVICE_SET_TEMPERATURE, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    EVENT_STATE_CHANGED,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .const import ACTIVE, DOMAIN, IDLE, LOGGER, SUPPORTED_HVAC_MODES
from .utils import filter_to_valid_areas, get_all_thermostat_entity_ids

PLATFORMS: list[Platform] = [Platform.CLIMATE]


def get_all_cover_entity_ids(areas):
    """Get all cover entity ids."""
    return [cover for area in areas.values() for cover in area.get("covers", [])]


def get_all_connectivity_entity_ids(areas):
    """Get all connectivity entity ids."""
    return [
        cover for area in areas.values() for cover in area.get("connectivities", [])
    ]


def get_all_temperature_entity_ids(areas):
    """Get all temperature entity ids."""
    return [area["temperature"] for area in areas.values() if "temperature" in area]


def determine_if_night_time_mode(areas):
    """Determine if night time mode."""
    return any(area.get("bedroom", False) for area in areas.values())


def determine_action(target_temperature: int, actual_temperature: int, hvac_mode: str):
    """Determine action."""
    if (
        hvac_mode in SUPPORTED_HVAC_MODES
        and target_temperature is not None
        and actual_temperature is not None
    ):
        modified_actual_temperature = int(float(actual_temperature))
        modified_target_temperature = int(float(target_temperature))
        match hvac_mode:
            case HVACMode.HEAT:
                if modified_actual_temperature >= modified_target_temperature:
                    return IDLE
            case HVACMode.COOL:
                if modified_actual_temperature <= modified_target_temperature:
                    return IDLE

    return ACTIVE


def determine_is_night_time(bed_time, wake_time):
    """Determine is night time."""
    timezone = dt_util.get_default_time_zone()
    now = datetime.datetime.now().astimezone(timezone)
    bed_time = datetime.time.fromisoformat(bed_time)
    wake_time = datetime.time.fromisoformat(wake_time)

    return (
        bed_time > wake_time
        and (now.time() > bed_time or now.time() < wake_time)
        or (bed_time <= wake_time and now.time() >= bed_time and now.time() < wake_time)
    )


def filter_to_bedrooms(areas):
    """Filter to bedrooms."""
    return {key: value for key, value in areas.items() if value.get("bedroom", False)}


def determine_cover_service_to_call(
    target_temperature: int,
    actual_temperature: int,
    hvac_mode: str,
    thermostat_action: str,
    is_night_time_mode: bool,
    is_night_time: bool,
    is_bedroom: bool,
    control_central_thermostat: bool,
) -> str:
    """Determine cover service."""
    if is_night_time_mode and is_night_time:
        return SERVICE_OPEN_COVER if is_bedroom else SERVICE_CLOSE_COVER
    action = (
        ACTIVE
        if thermostat_action == IDLE and control_central_thermostat is True
        else determine_action(target_temperature, actual_temperature, hvac_mode)
    )

    return SERVICE_CLOSE_COVER if action is not ACTIVE else SERVICE_OPEN_COVER


def determine_change_in_temperature(
    actual_temperature: float, hvac_mode: HVACMode, action: str
) -> float:
    """Determine change in temperature based on HVAC mode and action."""
    if hvac_mode in SUPPORTED_HVAC_MODES:
        match hvac_mode:
            case HVACMode.HEAT:
                difference_in_temperature = 2 if action == ACTIVE else -2
                return actual_temperature + difference_in_temperature
            case HVACMode.COOL:
                difference_in_temperature = -2 if action == ACTIVE else 2
                return actual_temperature + difference_in_temperature
    return actual_temperature


def determine_target_temperature(hass: HomeAssistant, area):
    """Determine thermostat temperature."""
    thermostat = hass.states.get("climate." + area + "_thermostat")
    return (
        thermostat.attributes["temperature"]
        if thermostat and "temperature" in thermostat.attributes
        else None
    )


def determine_actual_temperature(hass: HomeAssistant, devices):
    """Determine thermostat temperature."""
    temperature_sensor = hass.states.get(devices["temperature"])
    return temperature_sensor.state if temperature_sensor else None


def adjust_house(hass: HomeAssistant, config_entry: ConfigEntry):
    """Adjust house."""
    config_entry_data = config_entry.as_dict()["data"]
    central_thermostat_entity_ids = get_all_thermostat_entity_ids(config_entry_data)
    central_thermostat = hass.states.get(central_thermostat_entity_ids[0])
    if central_thermostat and "current_temperature" in central_thermostat.attributes:
        central_thermostat_actual_temperature = central_thermostat.attributes[
            "current_temperature"
        ]
        central_hvac_mode = central_thermostat.state
        config_entry_data_with_only_valid_areas = filter_to_valid_areas(
            config_entry_data
        )
        areas = config_entry_data_with_only_valid_areas.get("areas", {})
        bedroom_areas = filter_to_bedrooms(areas)
        is_night_time_mode = determine_if_night_time_mode(areas)
        is_night_time = determine_is_night_time(
            config_entry_data["bed_time"], config_entry_data["wake_time"]
        )
        control_central_thermostat = config_entry_data.get(
            "control_central_thermostat", False
        )
        thermostat_areas = (
            bedroom_areas if is_night_time_mode and is_night_time else areas
        )
        actions = [
            determine_action(
                determine_target_temperature(hass, area),
                determine_actual_temperature(hass, devices),
                central_hvac_mode,
            )
            for area, devices in thermostat_areas.items()
        ]
        thermostat_action = ACTIVE if ACTIVE in actions else IDLE
        for key, values in areas.items():
            area_thermostat = hass.states.get("climate." + key + "_thermostat")
            area_temperature_sensor = hass.states.get(values["temperature"])
            if (
                area_thermostat
                and "temperature" in area_thermostat.attributes
                and area_temperature_sensor
            ):
                area_actual_temperature = int(float(area_temperature_sensor.state))
                area_target_temperature = area_thermostat.attributes["temperature"]
                is_bedroom = values["bedroom"]
                service_to_call = determine_cover_service_to_call(
                    area_target_temperature,
                    area_actual_temperature,
                    central_hvac_mode,
                    thermostat_action,
                    is_night_time_mode,
                    is_night_time,
                    is_bedroom,
                    control_central_thermostat,
                )
                covers = values["covers"]
                LOGGER.info(
                    f"\nservice_to_call: {service_to_call}"
                    f"\ncovers: {covers}"
                    "\n--------------------------------------------------------"
                )
                for cover in covers:
                    hass.services.call(
                        Platform.COVER,
                        service_to_call,
                        service_data={ATTR_ENTITY_ID: cover},
                    )
        if control_central_thermostat:
            hass.services.call(
                Platform.CLIMATE,
                SERVICE_SET_TEMPERATURE,
                service_data={
                    ATTR_ENTITY_ID: central_thermostat_entity_ids[0],
                    ATTR_TEMPERATURE: determine_change_in_temperature(
                        central_thermostat_actual_temperature,
                        central_hvac_mode,
                        thermostat_action,
                    ),
                },
            )


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up HVAC Zoning from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    def handle_event_state_changed(event):
        event_dict = event.as_dict()
        data = event_dict["data"]
        entity_id = data["entity_id"]
        config_entry_data = config_entry.as_dict()["data"]
        config_entry_data_with_only_valid_areas = filter_to_valid_areas(
            config_entry_data
        )
        areas = config_entry_data_with_only_valid_areas.get("areas", {})
        # cover_entity_ids = get_all_cover_entity_ids(areas)
        connectivity_entity_ids = get_all_connectivity_entity_ids(areas)
        # temperature_entity_ids = get_all_temperature_entity_ids(areas)
        thermostat_entity_ids = get_all_thermostat_entity_ids(config_entry_data)
        virtual_thermostat_entity_ids = [
            "climate." + area + "_thermostat" for area in areas
        ]
        thermostat_entity_ids = thermostat_entity_ids + virtual_thermostat_entity_ids
        if entity_id in thermostat_entity_ids or (
            entity_id in connectivity_entity_ids
            and data["old_state"].state == STATE_OFF
            and data["new_state"].state == STATE_ON
        ):
            LOGGER.info(
                f"\nentity_id: {data['entity_id']}"
                + (f"\nold_state: {data['old_state']}" if "old_state" in data else "")
                + (f"\nnew_state: {data['new_state']}" if "new_state" in data else "")
                + "\n--------------------------------------------------------"
            )
            adjust_house(hass, config_entry)

    config_entry.async_on_unload(
        hass.bus.async_listen(EVENT_STATE_CHANGED, handle_event_state_changed)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
