"""Support for WundaSmart climate."""
from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp.client import ClientSession

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WundasmartDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

HVAC_ACTION_MAP = {
    "4": HVACAction.IDLE,
    "5": HVACAction.IDLE,
    "6": HVACAction.IDLE,
    "7": HVACAction.HEATING,
}

HVAC_MODE_MAP = {
    0: HVACMode.HEAT,
    1: HVACMode.OFF,
}

SUPPORTED_HVAC_MODES = [
    HVACMode.AUTO,
    HVACMode.HEAT,
]

PARALLEL_UPDATES = 1

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Wundasmart climate."""
    wunda_ip: str = entry.data[CONF_HOST]
    wunda_user: str = entry.data[CONF_USERNAME]
    wunda_pass: str = entry.data[CONF_PASSWORD]
    coordinator: WundasmartDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(
            aiohttp_client.async_get_clientsession(hass),
            wunda_ip,
            wunda_user,
            wunda_pass,
            device,
            coordinator,
        )
        for device in coordinator.data if device["type"] == "ROOM" and "name" in device
    )


class Device(CoordinatorEntity[WundasmartDataUpdateCoordinator], ClimateEntity):
    """Representation of an Wundasmart climate."""

    _attr_hvac_modes = SUPPORTED_HVAC_MODES
    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(
        self,
        session: ClientSession,
        wunda_ip: str,
        wunda_user: str,
        wunda_pass: str,
        device: dict[str, Any],
        coordinator: WundasmartDataUpdateCoordinator,
    ) -> None:
        """Initialize the Wundasmart climate."""
        super().__init__(coordinator)
        self._session = session
        self._wunda_ip = wunda_ip
        self._wunda_user = wunda_user
        self._wunda_pass = wunda_pass
        self._attr_name = device["name"].replace("%20", " ")
        self._attr_unique_id = device["id"]
        self._attr_type = device["type"]
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, device["id"]),
            },
            manufacturer="WundaSmart",
            name=self.name.replace("%20", " "),
            model=device["type"]
        )
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_current_temperature = 0
        self._attr_target_temperature = 0
        self._attr_current_humidity = 0
        self._attr_hvac_mode = HVACMode.AUTO

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = next(
            (
                device
                for device in self.coordinator.data
                if device["id"] == self._attr_unique_id
            ),
            None,
        )
        if device is not None and "state" in device and device["type"] == "ROOM":
            state = device["state"]
            if "room_temp" in state:
                self._attr_current_temperature = state["room_temp"]
            if "h" in state:
                self._attr_current_humidity = state["h"]
            if "sp" in state:
                self._attr_target_temperature = state["sp"]
            if "heat" in state:
                self._attr_hvac_action = HVAC_ACTION_MAP[state["heat"]]
            if "tp" in state:
                self._attr_hvac_mode = HVACMode.AUTO if state["tp"] == 32 else HVACMode.HEAT
            if "off" in state:
                if state["off"] == 1:
                    self._attr_hvac_mode = HVACMode.OFF
                    self._attr_hvac_action = HVACAction.OFF
                if "off" in state:
                    if state["off"] == 1: self._attr_hvac_action = HVACAction.OFF
            if "off" in state:
                self._attr_hvac_mode = HVAC_MODE_MAP[state["off"]]
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
