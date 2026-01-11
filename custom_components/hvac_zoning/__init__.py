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
    covers = [cover for area in areas.values() for cover in area.get("covers", [])]
    LOGGER.info("hvac_zoning: get_all_cover_entity_ids: Found covers=%s", covers)
    return covers


def get_all_connectivity_entity_ids(areas):
    """Get all connectivity entity ids."""
    connectivities = [
        cover for area in areas.values() for cover in area.get("connectivities", [])
    ]
    LOGGER.info("hvac_zoning: get_all_connectivity_entity_ids: Found connectivities=%s", connectivities)
    return connectivities


def get_all_temperature_entity_ids(areas):
    """Get all temperature entity ids."""
    temps = [area["temperature"] for area in areas.values() if "temperature" in area]
    LOGGER.info("hvac_zoning: get_all_temperature_entity_ids: Found temperature_sensors=%s", temps)
    return temps


def determine_if_night_time_mode(areas):
    """Determine if night time mode."""
    result = any(area.get("bedroom", False) for area in areas.values())
    LOGGER.info("hvac_zoning: determine_if_night_time_mode: areas=%s, result=%s", list(areas.keys()), result)
    return result


def determine_action(target_temperature: int, actual_temperature: int, hvac_mode: str):
    """Determine action."""
    LOGGER.info(
        "determine_action: target_temperature=%s, actual_temperature=%s, hvac_mode=%s",
        target_temperature,
        actual_temperature,
        hvac_mode,
    )
    if (
        hvac_mode in SUPPORTED_HVAC_MODES
        and target_temperature is not None
        and actual_temperature is not None
    ):
        modified_actual_temperature = int(float(actual_temperature))
        modified_target_temperature = int(float(target_temperature))
        LOGGER.info(
            "determine_action: modified_actual_temperature=%s, modified_target_temperature=%s",
            modified_actual_temperature,
            modified_target_temperature,
        )
        match hvac_mode:
            case HVACMode.HEAT:
                if modified_actual_temperature >= modified_target_temperature:
                    LOGGER.info("hvac_zoning: determine_action: HEAT mode, actual >= target, returning IDLE")
                    return IDLE
            case HVACMode.COOL:
                if modified_actual_temperature <= modified_target_temperature:
                    LOGGER.info("hvac_zoning: determine_action: COOL mode, actual <= target, returning IDLE")
                    return IDLE
    else:
        LOGGER.info(
            "determine_action: Conditions not met - hvac_mode in SUPPORTED_HVAC_MODES=%s, target_temperature is not None=%s, actual_temperature is not None=%s",
            hvac_mode in SUPPORTED_HVAC_MODES,
            target_temperature is not None,
            actual_temperature is not None,
        )

    LOGGER.info("hvac_zoning: determine_action: returning ACTIVE")
    return ACTIVE


def determine_is_night_time(bed_time, wake_time):
    """Determine is night time."""
    now = dt_util.now()
    LOGGER.info("hvac_zoning: determine_is_night_time: bed_time=%s, wake_time=%s, now=%s", bed_time, wake_time, now)
    bed_time = datetime.time.fromisoformat(bed_time)
    wake_time = datetime.time.fromisoformat(wake_time)

    result = (
        bed_time > wake_time
        and (now.time() > bed_time or now.time() < wake_time)
        or (bed_time <= wake_time and now.time() >= bed_time and now.time() < wake_time)
    )
    LOGGER.info("hvac_zoning: determine_is_night_time: result=%s", result)
    return result


def filter_to_bedrooms(areas):
    """Filter to bedrooms."""
    bedrooms = {key: value for key, value in areas.items() if value.get("bedroom", False)}
    LOGGER.info("hvac_zoning: filter_to_bedrooms: input_areas=%s, bedrooms=%s", list(areas.keys()), list(bedrooms.keys()))
    return bedrooms


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
    LOGGER.info(
        "determine_cover_service_to_call: target_temperature=%s, actual_temperature=%s, hvac_mode=%s, "
        "thermostat_action=%s, is_night_time_mode=%s, is_night_time=%s, is_bedroom=%s, control_central_thermostat=%s",
        target_temperature,
        actual_temperature,
        hvac_mode,
        thermostat_action,
        is_night_time_mode,
        is_night_time,
        is_bedroom,
        control_central_thermostat,
    )
    if is_night_time_mode and is_night_time:
        result = SERVICE_OPEN_COVER if is_bedroom else SERVICE_CLOSE_COVER
        LOGGER.info("hvac_zoning: determine_cover_service_to_call: Night time mode active, is_bedroom=%s, returning %s", is_bedroom, result)
        return result
    action = (
        ACTIVE
        if thermostat_action == IDLE and control_central_thermostat is True
        else determine_action(target_temperature, actual_temperature, hvac_mode)
    )
    LOGGER.info("hvac_zoning: determine_cover_service_to_call: action=%s (thermostat_action=%s, control_central_thermostat=%s)", action, thermostat_action, control_central_thermostat)

    result = SERVICE_CLOSE_COVER if action is not ACTIVE else SERVICE_OPEN_COVER
    LOGGER.info("hvac_zoning: determine_cover_service_to_call: returning %s", result)
    return result


def determine_change_in_temperature(
    actual_temperature: float, hvac_mode: HVACMode, action: str
) -> float:
    """Determine change in temperature based on HVAC mode and action."""
    LOGGER.info(
        "determine_change_in_temperature: actual_temperature=%s, hvac_mode=%s, action=%s",
        actual_temperature,
        hvac_mode,
        action,
    )
    if hvac_mode in SUPPORTED_HVAC_MODES and action == ACTIVE:
        match hvac_mode:
            case HVACMode.HEAT:
                result = actual_temperature + 2
                LOGGER.info("hvac_zoning: determine_change_in_temperature: HEAT mode, returning %s", result)
                return result
            case HVACMode.COOL:
                result = actual_temperature - 2
                LOGGER.info("hvac_zoning: determine_change_in_temperature: COOL mode, returning %s", result)
                return result
    LOGGER.info("hvac_zoning: determine_change_in_temperature: No change, returning %s", actual_temperature)
    return actual_temperature


def determine_target_temperature(hass: HomeAssistant, area):
    """Determine thermostat temperature."""
    entity_id = "climate." + area + "_thermostat"
    thermostat = hass.states.get(entity_id)
    LOGGER.info("hvac_zoning: determine_target_temperature: area=%s, entity_id=%s, thermostat=%s", area, entity_id, thermostat)
    if thermostat:
        LOGGER.info("hvac_zoning: determine_target_temperature: thermostat.attributes=%s", thermostat.attributes)
    result = (
        thermostat.attributes["temperature"]
        if thermostat and "temperature" in thermostat.attributes
        else None
    )
    LOGGER.info("hvac_zoning: determine_target_temperature: returning %s", result)
    return result


def determine_actual_temperature(hass: HomeAssistant, devices):
    """Determine thermostat temperature."""
    entity_id = devices["temperature"]
    temperature_sensor = hass.states.get(entity_id)
    LOGGER.info("hvac_zoning: determine_actual_temperature: entity_id=%s, temperature_sensor=%s", entity_id, temperature_sensor)
    result = temperature_sensor.state if temperature_sensor else None
    LOGGER.info("hvac_zoning: determine_actual_temperature: returning %s", result)
    return result


def adjust_house(hass: HomeAssistant, config_entry: ConfigEntry):
    """Adjust house."""
    LOGGER.info("hvac_zoning: adjust_house: Starting house adjustment")
    config_entry_data = config_entry.as_dict()["data"]
    LOGGER.info("hvac_zoning: adjust_house: config_entry_data=%s", config_entry_data)
    central_thermostat_entity_ids = get_all_thermostat_entity_ids(config_entry_data)
    LOGGER.info("hvac_zoning: adjust_house: central_thermostat_entity_ids=%s", central_thermostat_entity_ids)
    if not central_thermostat_entity_ids:
        LOGGER.warning("hvac_zoning: adjust_house: No central thermostat entity IDs found, exiting")
        return
    central_thermostat = hass.states.get(central_thermostat_entity_ids[0])
    LOGGER.info("hvac_zoning: adjust_house: central_thermostat=%s", central_thermostat)
    if central_thermostat:
        LOGGER.info("hvac_zoning: adjust_house: central_thermostat.state=%s, central_thermostat.attributes=%s", central_thermostat.state, central_thermostat.attributes)
    if central_thermostat and "current_temperature" in central_thermostat.attributes:
        central_thermostat_actual_temperature = central_thermostat.attributes[
            "current_temperature"
        ]
        central_hvac_mode = central_thermostat.state
        LOGGER.info(
            "adjust_house: central_thermostat_actual_temperature=%s, central_hvac_mode=%s",
            central_thermostat_actual_temperature,
            central_hvac_mode,
        )
        config_entry_data_with_only_valid_areas = filter_to_valid_areas(
            config_entry_data
        )
        areas = config_entry_data_with_only_valid_areas.get("areas", {})
        LOGGER.info("hvac_zoning: adjust_house: valid areas=%s", list(areas.keys()))
        bedroom_areas = filter_to_bedrooms(areas)
        is_night_time_mode = determine_if_night_time_mode(areas)
        is_night_time = determine_is_night_time(
            config_entry_data["bed_time"], config_entry_data["wake_time"]
        )
        LOGGER.info(
            "adjust_house: is_night_time_mode=%s, is_night_time=%s, bedroom_areas=%s",
            is_night_time_mode,
            is_night_time,
            list(bedroom_areas.keys()),
        )
        control_central_thermostat = config_entry_data.get(
            "control_central_thermostat", False
        )
        LOGGER.info("hvac_zoning: adjust_house: control_central_thermostat=%s", control_central_thermostat)
        thermostat_areas = (
            bedroom_areas if is_night_time_mode and is_night_time else areas
        )
        LOGGER.info("hvac_zoning: adjust_house: thermostat_areas=%s", list(thermostat_areas.keys()))
        actions = [
            determine_action(
                determine_target_temperature(hass, area),
                determine_actual_temperature(hass, devices),
                central_hvac_mode,
            )
            for area, devices in thermostat_areas.items()
        ]
        thermostat_action = ACTIVE if ACTIVE in actions else IDLE
        LOGGER.info("hvac_zoning: adjust_house: actions=%s, thermostat_action=%s", actions, thermostat_action)
        for key, values in areas.items():
            LOGGER.info("hvac_zoning: adjust_house: Processing area=%s, values=%s", key, values)
            area_thermostat = hass.states.get("climate." + key + "_thermostat")
            area_temperature_sensor = hass.states.get(values["temperature"])
            LOGGER.info(
                "adjust_house: area=%s, area_thermostat=%s, area_temperature_sensor=%s",
                key,
                area_thermostat,
                area_temperature_sensor,
            )
            if area_thermostat:
                LOGGER.info("hvac_zoning: adjust_house: area=%s, area_thermostat.attributes=%s", key, area_thermostat.attributes)
            if (
                area_thermostat
                and "temperature" in area_thermostat.attributes
                and area_temperature_sensor
            ):
                area_actual_temperature = int(float(area_temperature_sensor.state))
                area_target_temperature = area_thermostat.attributes["temperature"]
                is_bedroom = values["bedroom"]
                LOGGER.info(
                    "adjust_house: area=%s, area_actual_temperature=%s, area_target_temperature=%s, is_bedroom=%s",
                    key,
                    area_actual_temperature,
                    area_target_temperature,
                    is_bedroom,
                )
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
                    "adjust_house: area=%s, service_to_call=%s, covers=%s",
                    key,
                    service_to_call,
                    covers,
                )
                for cover in covers:
                    LOGGER.info("hvac_zoning: adjust_house: Calling service %s for cover %s", service_to_call, cover)
                    hass.services.call(
                        Platform.COVER,
                        service_to_call,
                        service_data={ATTR_ENTITY_ID: cover},
                    )
            else:
                LOGGER.warning(
                    "adjust_house: Skipping area=%s - area_thermostat=%s, has_temperature_attr=%s, area_temperature_sensor=%s",
                    key,
                    area_thermostat is not None,
                    "temperature" in area_thermostat.attributes if area_thermostat else False,
                    area_temperature_sensor is not None,
                )
        if control_central_thermostat:
            new_temp = determine_change_in_temperature(
                central_thermostat_actual_temperature,
                central_hvac_mode,
                thermostat_action,
            )
            LOGGER.info(
                "adjust_house: Setting central thermostat temperature to %s (entity_id=%s)",
                new_temp,
                central_thermostat_entity_ids[0],
            )
            hass.services.call(
                Platform.CLIMATE,
                SERVICE_SET_TEMPERATURE,
                service_data={
                    ATTR_ENTITY_ID: central_thermostat_entity_ids[0],
                    ATTR_TEMPERATURE: new_temp,
                },
            )
        LOGGER.info("hvac_zoning: adjust_house: House adjustment complete")
    else:
        LOGGER.warning(
            "adjust_house: Central thermostat not available or missing current_temperature attribute. "
            "central_thermostat=%s, has_current_temperature=%s",
            central_thermostat is not None,
            "current_temperature" in central_thermostat.attributes if central_thermostat else False,
        )


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up HVAC Zoning from a config entry."""
    LOGGER.info("hvac_zoning: async_setup_entry: Starting HVAC Zoning setup")
    LOGGER.info("hvac_zoning: async_setup_entry: config_entry=%s", config_entry.as_dict())

    hass.data.setdefault(DOMAIN, {})

    LOGGER.info("hvac_zoning: async_setup_entry: Forwarding entry setups for platforms=%s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    LOGGER.info("hvac_zoning: async_setup_entry: Platform setup complete")

    def handle_event_state_changed(event):
        event_dict = event.as_dict()
        data = event_dict["data"]
        entity_id = data["entity_id"]
        LOGGER.info("handle_event_state_changed: Received event for entity_id=%s", entity_id)
        config_entry_data = config_entry.as_dict()["data"]
        config_entry_data_with_only_valid_areas = filter_to_valid_areas(
            config_entry_data
        )
        areas = config_entry_data_with_only_valid_areas.get("areas", {})
        connectivity_entity_ids = get_all_connectivity_entity_ids(areas)
        thermostat_entity_ids = get_all_thermostat_entity_ids(config_entry_data)
        virtual_thermostat_entity_ids = [
            "climate." + area + "_thermostat" for area in areas
        ]
        thermostat_entity_ids = thermostat_entity_ids + virtual_thermostat_entity_ids
        LOGGER.info(
            "handle_event_state_changed: thermostat_entity_ids=%s, connectivity_entity_ids=%s",
            thermostat_entity_ids,
            connectivity_entity_ids,
        )

        is_thermostat_event = entity_id in thermostat_entity_ids
        is_connectivity_event = (
            entity_id in connectivity_entity_ids
            and data["old_state"].state == STATE_OFF
            and data["new_state"].state == STATE_ON
        )
        LOGGER.info(
            "handle_event_state_changed: entity_id=%s, is_thermostat_event=%s, is_connectivity_event=%s",
            entity_id,
            is_thermostat_event,
            is_connectivity_event,
        )

        if is_thermostat_event or is_connectivity_event:
            LOGGER.info(
                "handle_event_state_changed: Triggering adjust_house for entity_id=%s, "
                "old_state=%s, new_state=%s",
                data["entity_id"],
                data.get("old_state"),
                data.get("new_state"),
            )
            adjust_house(hass, config_entry)
        else:
            LOGGER.info(
                "handle_event_state_changed: Ignoring event for entity_id=%s (not a monitored entity)",
                entity_id,
            )

    LOGGER.info("hvac_zoning: async_setup_entry: Registering EVENT_STATE_CHANGED listener")
    config_entry.async_on_unload(
        hass.bus.async_listen(EVENT_STATE_CHANGED, handle_event_state_changed)
    )

    LOGGER.info("hvac_zoning: async_setup_entry: HVAC Zoning setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
