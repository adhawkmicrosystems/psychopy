# -*- coding: utf-8 -*-
# Part of the PsychoPy library
# Copyright (C) 2012-2020 iSolver Software Solutions (C) 2021 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).


import time

import adhawkapi
import gevent
from psychopy import visual
from psychopy.iohub.constants import EventConstants as EC
from psychopy.iohub.devices import Computer, DeviceEvent
from psychopy.iohub.devices.keyboard import KeyboardInputEvent
from psychopy.iohub.errors import print2err
from psychopy.iohub.util import convertCamelToSnake, updateSettings

currentTime = Computer.getTime
INSTRUCTION_MSG = 'Press SPACE to Start Adhawk Calibration; ESCAPE to Exit.'


class AdhawkPsychopyCalibrationGraphics:
    IOHUB_HEARTBEAT_INTERVAL = 0.050
    timeout = 5  # second
    _keyboard_key_index = KeyboardInputEvent.CLASS_ATTRIBUTE_NAMES.index('key')

    def __init__(self, eyetracker_interface, calibration_args, frontend_api):

        self._eyetracker = eyetracker_interface
        self._frontend_api = frontend_api
        self._frontend_api.register_stream_handler(adhawkapi.PacketType.EVENTS, self._handleEvents)
        self._frontend_api.set_event_control(adhawkapi.EventControlBit.PRODECURE_START_END, 1,
                                             callback=(lambda *args: None))

        self._autotune_ended = False
        self._calibration_ended = False
        self._autotune_successful = False
        self._calibration_successful = False
        self._timeout_time_start = 0

        self.screenSize = eyetracker_interface._display_device.getPixelResolution()
        self.width = self.screenSize[0]
        self.height = self.screenSize[1]
        self._ioKeyboard = None
        self._msg_queue = []

        self._device_config = self._eyetracker.getConfiguration()
        display = self._eyetracker._display_device

        updateSettings(self._device_config.get('calibration'), calibration_args)
        self._calibration_args = self._device_config.get('calibration')
        unit_type = self._getCalibSetting('unit_type')
        if unit_type is None:
            unit_type = display.getCoordinateType()
            self._calibration_args['unit_type'] = unit_type
        color_type = self._getCalibSetting('color_type')
        if color_type is None:
            color_type = display.getColorSpace()
            self._calibration_args['color_type'] = color_type

        self.window = visual.Window(
            self.screenSize,
            monitor=display.getPsychopyMonitorName(),
            units=unit_type,
            fullscr=True,
            allowGUI=False,
            screen=display.getIndex(),
            color=self._getCalibSetting(['screen_background_color']),
            colorSpace=color_type)
        self.window.flip(clearBuffer=True)

        self._createStim()
        self._registerEventMonitors()
        self._lastMsgPumpTime = currentTime()

        self._clearAllEventBuffers()

    def runCalibration(self):
        """ Initiate and run the Adhawk calibration procedure """
        calibration_methods = dict(THREE_POINTS=3,
                                   FIVE_POINTS=5,
                                   NINE_POINTS=9,
                                   THIRTEEN_POINTS=13)

        if self._getCalibSetting('type') in calibration_methods:
            num_points = calibration_methods[self._getCalibSetting('type')]

        instuction_text = INSTRUCTION_MSG
        res = self._showSystemSetupMessageScreen(instuction_text)

        self._clearCalibrationWindow()
        self.window.winHandle.set_visible(False)
        self.window.winHandle.minimize()
        gevent.sleep(self.IOHUB_HEARTBEAT_INTERVAL)

        if not res:  # user pressed esc key to skip the calibration
            self._autotune_ended = True
            self._calibration_ended = True
            print2err(f'Adhawk calibration skipped')
            return self._calibration_successful

        self._frontend_api.autotune_gui(mode=adhawkapi.MarkerSequenceMode.FIXED_HEAD.value,
                                        marker_size_mm=35, callback=self._handleCalibrationGuiResponse)

        while not self._autotune_ended and not self._should_stop():
            gevent.sleep(self.IOHUB_HEARTBEAT_INTERVAL)

        if self._autotune_successful:
            self._timeout_time_start = 0
            self._frontend_api.start_calibration_gui(mode=adhawkapi.MarkerSequenceMode.FIXED_HEAD.value,
                                                     n_points=num_points, marker_size_mm=35,
                                                     randomize=self._calibration_args.get('randomize'),
                                                     callback=self._handleCalibrationGuiResponse)
            while not self._calibration_ended and not self._should_stop():
                gevent.sleep(self.IOHUB_HEARTBEAT_INTERVAL)

        self._unregisterEventMonitors()
        self._clearAllEventBuffers()
        return self._calibration_successful

    def _should_stop(self):
        if not self._timeout_time_start:
            return False
        return (time.perf_counter() - self._timeout_time_start) > self.timeout

    def _getCalibSetting(self, setting):
        if isinstance(setting, str):
            setting = [setting, ]
        calibration_args = self._calibration_args
        if setting:
            for s in setting[:-1]:
                calibration_args = calibration_args.get(s)
            return calibration_args.get(setting[-1])

    def _clearAllEventBuffers(self):
        self._eyetracker._iohub_server.eventBuffer.clear()
        for d in self._eyetracker._iohub_server.devices:
            d.clearEvents()

    def _registerEventMonitors(self):
        kbDevice = None
        if self._eyetracker._iohub_server:
            for dev in self._eyetracker._iohub_server.devices:
                if dev.__class__.__name__ == 'Keyboard':
                    kbDevice = dev

        if kbDevice:
            eventIDs = []
            for event_class_name in kbDevice.__class__.EVENT_CLASS_NAMES:
                eventIDs.append(getattr(EC, convertCamelToSnake(event_class_name[:-5], False)))

            self._ioKeyboard = kbDevice
            self._ioKeyboard._addEventListener(self, eventIDs)
        else:
            print2err('Warning: Calibration GFX could not connect to Keyboard device for events.')

    def _unregisterEventMonitors(self):
        if self._ioKeyboard:
            self._ioKeyboard._removeEventListener(self)

    def _handleEvent(self, event):
        event_type_index = DeviceEvent.EVENT_TYPE_ID_INDEX
        if event[event_type_index] == EC.KEYBOARD_PRESS:
            ek = event[self._keyboard_key_index]
            if isinstance(ek, bytes):
                ek = ek.decode('utf-8')
            if ek == ' ' or ek == 'space':
                self._msg_queue.append('SPACE_KEY_ACTION')
                self._clearAllEventBuffers()
            elif ek == 'escape':
                self._timeout_time_start = time.perf_counter()
                self._msg_queue.append('QUIT')
                self._clearAllEventBuffers()

    def _msgPump(self):
        # keep the psychopy window happy ;)
        if currentTime() - self._lastMsgPumpTime > self.IOHUB_HEARTBEAT_INTERVAL:
            # try to keep ioHub from being blocked. ;(
            if self._eyetracker._iohub_server:
                for dm in self._eyetracker._iohub_server.deviceMonitors:
                    dm.device._poll()
                self._eyetracker._iohub_server.processDeviceEvents()
            self._lastMsgPumpTime = currentTime()

    def _getNextMsg(self):
        if len(self._msg_queue) > 0:
            msg = self._msg_queue[0]
            self._msg_queue = self._msg_queue[1:]
            return msg

    def _createStim(self):
        color_type = self._getCalibSetting('color_type')

        tctype = color_type
        tcolor = self._getCalibSetting(['text_color'])
        if tcolor is None:
            # If no calibration text color provided, base it on the window background color
            from psychopy.iohub.util import complement
            sbcolor = self._getCalibSetting(['screen_background_color'])
            if sbcolor is None:
                sbcolor = self.window.color
            from psychopy.colors import Color
            tcolor_obj = Color(sbcolor, color_type)
            tcolor = complement(*tcolor_obj.rgb255)
            tctype = 'rgb255'

        self.textLineStim = visual.TextStim(self.window, text=INSTRUCTION_MSG,
                                            pos=(0, 0), height=36,
                                            color=tcolor, colorSpace=tctype,
                                            units='pix', wrapWidth=self.width * 0.9)

    def _clearCalibrationWindow(self):
        self.window.flip(clearBuffer=True)

    def _showSystemSetupMessageScreen(self, text_msg=INSTRUCTION_MSG):

        self._clearAllEventBuffers()

        while True:
            self.textLineStim.setText(text_msg)
            self.textLineStim.draw()
            self.window.flip()

            msg = self._getNextMsg()
            if msg == 'SPACE_KEY_ACTION':
                self._clearAllEventBuffers()
                return True
            elif msg == 'QUIT':
                self._clearAllEventBuffers()
                return False
            self._msgPump()
            gevent.sleep(self.IOHUB_HEARTBEAT_INTERVAL)

    def _handleEvents(self, event_type, _timestamp, *args):
        """Receives procedure start and stop events. This implementation checks for
        the end of a calibration routine and the result of said routine"""
        if event_type == adhawkapi.Events.PROCEDURE_ENDED:
            if not self._autotune_ended:
                if args[0] != adhawkapi.AckCodes.SUCCESS:
                    print2err(f'Failed to start the Adhawk calibration: {adhawkapi.errormsg(args[0])}')
                else:
                    self._autotune_successful = True
                self._autotune_ended = True
            else:
                if args[0] != adhawkapi.AckCodes.SUCCESS:
                    print2err(f'Failed to calibrate eye tracker: {adhawkapi.errormsg(args[0])}')
                else:
                    self._calibration_successful = True
                self._calibration_ended = True

    def _handleCalibrationGuiResponse(self, *args, **kwargs):
        if args[0] != adhawkapi.AckCodes.SUCCESS:
            self._autotune_ended = True
            self._calibration_ended = True
            print2err(f'Unable to start the Adhawk calibration: {adhawkapi.errormsg(args[0])}')
