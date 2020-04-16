import logging
import voluptuous as vol
import json
import asyncio
import async_timeout
import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_TIMEOUT, STATE_OFF, STATE_ON)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

LOGGING = logging.getLogger(__name__)
SUPPORTED_FEATURES_MONO = (SUPPORT_BRIGHTNESS)
DEFAULT_NAME = 'Blebox wLightBoxS'
DEFAULT_RELAY = 0
DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    timeout = config.get(CONF_TIMEOUT)

    light = BleboxWlightBoxSLight(name, host, timeout)
    yield from light.async_device_init(hass)
    async_add_devices([light])


class BleboxWlightBoxSLight(Light):
    def __init__(self, name, host, timeout):
        self._name = name
        self._host = host
        self._timeout = timeout
        self._state = False
        self._hs_color = (0, 0)
        self._brightness = 255
        self._available = False

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, state):
        self._state = STATE_ON if state else STATE_OFF

    @property
    def is_on(self):
        return self._state == STATE_ON

    @property
    def available(self):
        return self._available

    @property
    def brightness(self):
        return self._brightness

    @property
    def supported_features(self):
        return SUPPORTED_FEATURES_MONO

    @asyncio.coroutine
    def async_device_init(self, hass):
        device_info = yield from self.async_update_device_info(hass)

        if not self._name:
            self._name = device_info['device']['deviceName'] if device_info else DEFAULT_NAME

        return device_info

    @asyncio.coroutine
    def async_update_device_info(self, hass):

        device_info = None

        try:
            device_info = yield from self.get_device_info(hass)
            self._available = True
            current_color = device_info['light']['desiredColor']
        except:
            self._available = False
            current_color = '00'

        if current_color != '00':
            self.state = True
            self._brightness = int(current_color, 16)
        else:
            self.state = False

        return device_info

    @asyncio.coroutine
    def async_update(self):
        yield from self.async_update_device_info(self.hass)

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        color = '{0:02x}'.format(self._brightness)

        yield from self.set_device_color(color, self._effect)

    @asyncio.coroutine
    def async_turn_off(self):
        yield from self.set_device_color('00')

    @asyncio.coroutine
    def set_device_color(self, color):
        websession = async_get_clientsession(self.hass)
        resource = 'http://%s/api/light/set' % self._host
        effect_id = LIGHT_EFFECT_LIST.index(effect)
        payload = '{"light": {"desiredColor": "%s"}}' % (color)

        try:
            with async_timeout.timeout(self._timeout, loop=self.hass.loop):
                req = yield from getattr(websession, 'post')(resource, data=bytes(payload, 'utf-8'))
                text = yield from req.text()
                return json.loads(text)['light']
        except:
            return None

    @asyncio.coroutine
    def get_device_info(self, hass):
        websession = async_get_clientsession(hass)
        resource = 'http://%s/api/device/state' % self._host

        try:
            with async_timeout.timeout(self._timeout, loop=hass.loop):
                req = yield from websession.get(resource)
                text = yield from req.text()
                device_info = json.loads(text)
                device = device_info['device']
                return device_info
        except:
            return None
