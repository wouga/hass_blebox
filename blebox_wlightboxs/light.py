"""Support for BleboxWlightBoxSLight lights."""
"""Script based on https://github.com/joncar/pyeverlights"""

from datetime import timedelta
import logging
import voluptuous as vol
import aiohttp
import asyncio
import json

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    Light,
)
from homeassistant.const import CONF_HOSTS
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = SUPPORT_BRIGHTNESS

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOSTS): vol.All(cv.ensure_list, [cv.string])}
)

class ConnectionError(Exception):
    pass


class BleboxWlightBoxS:
    def __init__(self, ip, session=None):
        self._ip = ip
        self._session = session
        self._auto_session = False

    async def _fetch_get(self, path, params=None):
        if not self._session:
            self._session = aiohttp.ClientSession()
            self._auto_session = True

        try:
            async with self._session.get('http://'+self._ip+path,
                                         params=params) as response:
                data = await response.json()
                _LOGGER.debug(str(response.url) + ' response: ' +
                              json.dumps(data, sort_keys=True, indent=4))
                return data
        except aiohttp.client_exceptions.ClientConnectorError as e:
            raise ConnectionError from e
        except asyncio.TimeoutError as e:
            raise ConnectionError from e
        except json.decoder.JSONDecodeError as e:
            raise ConnectionError from e

    async def _fetch_post(self, path, json={}):
        if not self._session:
            self._session = aiohttp.ClientSession()
            self._auto_session = True

        try:
            async with self._session.get('http://'+self._ip+path,
                                         json=json) as response:
                # _LOGGER.warning(response)
                data = await response.json()
                return data
        except aiohttp.client_exceptions.ClientConnectorError as e:
            raise ConnectionError from e
        except asyncio.TimeoutError as e:
            raise ConnectionError from e
        except json.decoder.JSONDecodeError as e:
            raise ConnectionError from e

    async def get_status(self):
        resp = await self._fetch_get('/api/device/state')
        return resp

    async def get_state(self):
        resp = await self._fetch_get('/api/light/state')
        return resp

    async def set_params(self, desiredColor="FF", fadeSpeed=213):
        json = {
            "light": {
            "desiredColor": desiredColor,
            "fadeSpeed": fadeSpeed
            }
        }

        resp = await self._fetch_post('/api/light/set',json=json)
        return resp

    async def set_brightness(self, brightness=255):
        resp = await self.set_params(format(brightness,'02x'))
        return resp


    async def close(self):
        if self._auto_session:
            await self._session.close()
            self._session = None
            self._auto_session = False


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the BleboxWlightBoxSLight lights from configuration.yaml."""

    lights = []

    for ipaddr in config[CONF_HOSTS]:
        api = BleboxWlightBoxS(ipaddr, async_get_clientsession(hass))

        try:
            status = await api.get_status()
            state = await api.get_state()

        except ConnectionError:
            raise PlatformNotReady

        else:
            lights.append(BleboxWlightBoxSLight(api, status, state))

    async_add_entities(lights)


class BleboxWlightBoxSLight(Light):
    """Representation of a Flux light."""

    def __init__(self, api, status, state):
        """Initialize the light."""
        self._api = api
        self._status = status
        self._state = state
        self._id = status["device"]["id"]
        self._type = status["device"]["type"]
        self._deviceName = status["device"]["deviceName"]
        self._error_reported = False
        self._brightness = int(state["light"]["desiredColor"],16)
        self._available = True

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._id}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def name(self):
        """Return the name of the device."""
        return f"BleboxWlightBoxSLight: #id: {self._id} #Name: {self._deviceName}"

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._type == "wLightBoxS"

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        await self._api.set_brightness(brightness)

        self._brightness = brightness

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._api.set_brightness(0)

    async def async_update(self):
        """Synchronize state with control box."""
        try:
            self._status = await self._api.get_status()
            self._state = await self._api.get_state()
            self._brightness = int(self._state["light"]["desiredColor"],16)

        except ConnectionError:
            if self._available:
                _LOGGER.warning("BleboxWlightBoxSLight control box connection lost.")
            self._available = False
        else:
            if not self._available:
                _LOGGER.warning("BleboxWlightBoxSLight control box connection restored.")
            self._available = True
