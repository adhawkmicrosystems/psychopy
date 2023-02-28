# -*- coding: utf-8 -*-
# Part of the PsychoPy library
# Copyright (C) 2012-2020 iSolver Software Solutions (C) 2021 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).
import time

import gevent
import pandas as pd
from psychopy.iohub.constants import EyeTrackerConstants
from psychopy.iohub.devices import Computer, Device
from psychopy.iohub.devices.eyetracker.eye_events import *
from psychopy.iohub.devices.eyetracker.hw.adhawk.adhawkCalibrationGraphics import \
    AdhawkPsychopyCalibrationGraphics
from psychopy.iohub.devices.eyetracker.hw.adhawk.helpers import *
from psychopy.iohub.errors import print2err, printExceptionDetailsToStdErr

try:
    import adhawkapi
    import adhawkapi.frontend
except Exception:
    print2err('Unable to import adhawkapi package. Please install AdHawk Python SDK and try again.')
    printExceptionDetailsToStdErr()

RESOLUTION = adhawkapi.CameraResolution.MEDIUM
MARKER_INFO_DEFAULT = pd.DataFrame(columns=['aruco_id', 'pos_x_cm', 'pos_y_cm', 'size_image_cm'])
ARUCO_DIC = 'DICT_5X5_50'

MARKERS_NOT_DEFINED_MSG = 'Markers not defined for screen tracking.'


class EyeTracker(EyeTrackerDevice):
    """
    Implementation of the :py:class:`Common Eye Tracker Interface <.EyeTrackerDevice>`
    for the AdHawk Microsystems MindLinks.

    This class operates with or without screen tracking, depending on if
    ``Enable screen tracking`` is selected in the ``Eyetracking`` tab of the
    ``experiment settings``.

    #. Screen tracking enabled
        Screen tracking is required to receive gaze data from AdHawk MindLinks in
        |PsychpPy| experiments. If screen tracking is enabled, binocular eye sample
        and blink event data is provided to users.

    #. Screen tracking disabled
        If screen tracking is disabled, gaze in screen data for AdHawk MindLinks is
        removed from binocular eye samples. Binocular eye samples and blink event data
        is still provided to users

    .. note::

        Only **one** instance of EyeTracker can be created within an experiment.
        Attempting to create > 1 instance will raise an exception.

    """
    #: The multiplier needed to convert a device's native time base to sec.msec-usec times.
    DEVICE_TIMEBASE_TO_SEC = 1.0

    EVENT_CLASS_NAMES = [
        "BinocularEyeSampleEvent",
        "BlinkEndEvent"]

    def __init__(self, *args, **kwargs):
        EyeTrackerDevice.__init__(self, *args, **kwargs)

        self._aruco_info = MARKER_INFO_DEFAULT
        self._screen_size = None
        self._physical_screen_dimensions = None
        # tools to halt code execution until connection secured with AdHawk glasses
        self._max_wait_time = 1  # seconds
        self._wait_interval_time = 0.001  # seconds
        self._connected = False
        self._camera_started = False

        self._latest_sample_timestamp = 0
        self._latest_gaze_in_screen = np.zeros(2, dtype=np.float64)
        self._latest_binocular_gaze_data = np.zeros(6, dtype=np.float64)
        self._latest_pupil_diameter_data = np.zeros(2, dtype=np.float64)

        self._sampling_rate = self._runtime_settings['sampling_rate']
        self._calibration_sampling_duration = int(self._runtime_settings['calibration_sampling_duration'])
        self._screen_tracking = self._runtime_settings['enable_screen_tracking']

        self._frontend_api = adhawkapi.frontend.FrontendApi()
        self.setConnectionState(True)

        # hold last received ioHub eye sample (in ordered array format) from tracker.
        self._latest_sample = None

        # holds the last gaze position read from the eye tracker as an x,y tuple. If binocular recording is
        # being performed, this is an average of the left and right gaze position x,y fields.
        # currently, not implemented as requires screen tracking
        self._latest_gaze_position = None

    def trackerTime(self):
        """trackerTime returns the current time reported by the eye tracker
        device. The time base is implementation dependent.
        # TODO ask what the best way to describe this is
        Args:
            None

        Return:
            float: The eye tracker hardware's reported current time.

        """
        return self._latest_sample_timestamp

    def trackerSec(self):
        """
        Returns :py:func:`.EyeTracker.trackerTime`

        Args:
            None

        :return: The eye tracker hardware's reported current time in sec.msec-usec format.
        """
        return self.trackerTime()

    def setConnectionState(self, enable: bool):
        """setConnectionState either connects ( setConnectionState(True) ) or
        disables ( setConnectionState(False) ) active communication between the
        ioHub and the AdHawk MindLinks.

        .. note::
            A connection to the Eye Tracker is automatically established
            when the ioHub Process is initialized (based on the device settings
            in the iohub_config.yaml), so there is no need to
            explicitly call this method in the experiment script.

        .. note::
            Connecting an Eye Tracker to the ioHub does **not** necessarily collect and send
            eye sample data to the ioHub Process. To start actual data collection,
            use the Eye Tracker method setRecordingState(bool) or the ioHub Device method (device type
            independent) enableEventRecording(bool).

        Args:
            enable (bool): True = enable the connection, False = disable the connection.

        :return:
            bool: indicates the current connection state to the eye tracking hardware.

        """
        if enable and not self.isConnected():
            # uses the AdHawk frontend to connect to backend
            self._frontend_api.register_stream_handler(adhawkapi.PacketType.EXTENDED_GAZE, self._handle_gaze_data)
            self._frontend_api.register_stream_handler(adhawkapi.PacketType.PER_EYE_GAZE,
                                                       self._handle_binocular_gaze_data)
            self._frontend_api.register_stream_handler(adhawkapi.PacketType.GAZE_IN_SCREEN,
                                                       self._handle_gaze_in_screen_data)
            self._frontend_api.register_stream_handler(adhawkapi.PacketType.PUPIL_DIAMETER, self._handle_pupil_diameter)
            self._frontend_api.register_stream_handler(adhawkapi.PacketType.EVENTS, self._handle_events)
            self._frontend_api.start(connect_cb=self._handle_connect)

            start_time = time.perf_counter()
            while not self._connected:
                if (time.perf_counter() - start_time) > self._max_wait_time:
                    break
                gevent.sleep(self._wait_interval_time)

            if not self.isConnected():
                print2err("Couldn't connect to the Adhawk Eye Tracker")

        elif not enable and self.isConnected() and self._frontend_api:
            # uses the Adhawk frontend to end the connection to backend
            if self._screen_tracking:
                self._stop_screen_tracking()
                self._stop_camera()
            self._frontend_api.shutdown()
            self._connected = False

        return self._connected

    def isConnected(self):
        """isConnected returns whether the ioHub EyeTracker Device is connected
        to the AdHawk MindLinks or not. The MindLinks must be connected to
        the ioHub for any of the Common Eye Tracker Interface functionality to
        work.

        Args:
            None

        Return:
            bool:  True = the eye tracking hardware is connected. False otherwise.

        """
        return self._connected

    def sendCommand(self, key, value=None):
        """
        In general, eye tracker implementations should **not** need to support
        this method unless there is critical eye tracker functionality that is
        not accessible using the other methods in the EyeTrackerDevice class.
        """
        return EyeTrackerConstants.FUNCTIONALITY_NOT_SUPPORTED

    def sendMessage(self, message_contents, time_offset=None):
        """The sendMessage method sends a text message to the eye tracker.

        Messages are generally used to send information you want
        saved with the native eye data file and are often used to
        synchronize stimulus changes in the experiment with the eye
        data stream being saved to the native eye tracker data file (if any).

        This means that the sendMessage implementation needs to
        perform in real-time, with a delay of <1 msec from when a message is
        sent to when it is time stamped by the eye tracker, for it to be
        accurate in this regard.

        If this standard can not be met, the expected delay and message
        timing precision (variability) should be provided in the eye tracker's
        implementation notes.

        .. note::
            If using the ioDataStore to save the eye tracker data, the use of
            this method is quite optional, as Experiment Device Message Events
            will likely be preferred. ioHub Message Events are stored in the ioDataStore,
            alongside all other device data collected via the ioHub, and not
            in the native eye tracker data.

        Args:
           message_contents (str):
               If message_contents is a string, check with the implementations documentation if there are any string length limits.

        Kwargs:
           time_offset (float): sec.msec_usec time offset that the time stamp of
                              the message should be offset in the eye tracker data file.
                              time_offset can be used so that a message can be sent
                              for a display change **BEFORE** or **AFTER** the actual
                              flip occurred, using the following formula:

                              time_offset = sendMessage_call_time - event_time_message_represent

                              Both times should be based on the iohub.devices.Computer.getTime() time base.

                              If time_offset is not supported by the eye tracker implementation being used, a warning message will be printed to stdout.

        Return:
            (int): EyeTrackerConstants.EYETRACKER_OK, EyeTrackerConstants.EYETRACKER_ERROR, or EyeTrackerConstants.EYETRACKER_INTERFACE_METHOD_NOT_SUPPORTED

        """

        return EyeTrackerConstants.FUNCTIONALITY_NOT_SUPPORTED

    def runSetupProcedure(self, calibration_args={}):
        """
        The runSetupProcedure method starts the AdHawk calibration choreography. As AdHawk
        MindLinks are a wearable eyetracker instead of a remote eyetracker, the calibration
        routine is camera based instead of screen based. This results in all ``Target`` and
        ``Animation`` tab calibration arguments being ignored. ``Basic`` calibration arguments are
        still used when running the AdHawk calibration choreography.

        .. note::
            This is a blocking call for the PsychoPy Process and will not return to the
            experiment script until the calibration procedure was either successful,
            aborted, or failed.

        :param calibration_args: Accepts and implements Basic calibration arguments. Target
        and Animation calibration arguments are ignored.

        # TODO should we use this return format here, or stick with True and False
        :return:
            - :py:attr:`.EyeTrackerConstants.EYETRACKER_OK`
                if the calibration was succesful
            - :py:attr:`.EyeTrackerConstants.EYETRACKER_SETUP_ABORTED`
                if the choreography was aborted by the user
            - :py:attr:`.EyeTrackerConstants.EYETRACKER_CALIBRATION_ERROR`
                if the calibration failed, check logs for details
            - :py:attr:`.EyeTrackerConstants.EYETRACKER_ERROR`
                if any other error occured, check logs for details
        """
        if not self.isConnected():
            print2err('Unable to start calibration: Eye tracker not connected')
            return False
        self._frontend_api.set_camera_user_settings(adhawkapi.CameraUserSettings.SAMPLING_DURATION,
                                                    self._calibration_sampling_duration, callback=lambda *x: None)

        # start the front facing camera
        self._start_camera()
        if not self._camera_started:
            print2err('Unable to start calibration: Camera not started')
            return

        genv = AdhawkPsychopyCalibrationGraphics(self, calibration_args, self._frontend_api)

        calibration_ok = genv.runCalibration()

        genv.window.close()

        if not self._screen_tracking:
            self._stop_camera()
        else:
            self._start_screen_tracking()

        if not calibration_ok:
            self._stop_camera()
            print2err('Eye tracker calibration not successful')

        return calibration_ok

    def setRecordingState(self, recording):
        """The setRecordingState method is used to start or stop the recording
        and transmission of binocular and blink eye data from the connected AdHawk
        MindLinks to the ioHub Process.

        Args:
            recording (bool): if True, the eye tracker will start recording data.;
            false = stop recording data.

        :return:
            bool: the current recording state of the eye tracking device

        """
        if recording and self._connected and self._screen_tracking:
            self._start_camera()
            self._initiate_screen_tracking()
            self._start_screen_tracking()
            self._is_reporting_events = True
            return EyeTrackerDevice.enableEventReporting(self, True)

        self._stop_camera()
        self._stop_screen_tracking()
        self._latest_sample = None
        self._latest_gaze_position = None
        self._is_reporting_events = False
        return EyeTrackerDevice.enableEventReporting(self, False)

    def isRecordingEnabled(self):
        """The isRecordingEnabled method indicates if the AdHawk MindLinks are
        currently recording data.

        Args:
           None

        :return:
            bool: True == the device is recording data; False == Recording is not
            occurring

        """
        return self._is_reporting_events

    def getLastSample(self):
        """The getLastSample method returns the most recent binocular eye sample received
        from the AdHawk MindLinks. The MindLinks must be in a recording state for
        a sample event to be returned, otherwise None is returned.

        Args:
            None

        :returns:
            None: If the eye tracker is not currently recording data.

            BinocularEyeSample:  If the eye tracker is recording, the latest binocular sample event is returned.

        """
        return self._latest_sample

    def getLastGazePosition(self):
        """The getLastGazePosition method returns the most recent eye gaze
        position received from the AdHawk MindLinks. This is the position on the
        calibrated 2D surface that the eye tracker is reporting as the current
        eye position. The units are in the units in use by the ioHub Display
        device.

        The average x and y position of both eyes is returned.

        If no samples have been received from the eye tracker, or the
        eye tracker is not currently recording data, None is returned.

        Args:
            None

        Returns:
            None: If the eye tracker is not currently recording data or no eye samples
            have been received.

            tuple: Latest (gaze_x,gaze_y) position of the eyes in display coordinates.
        """
        return self._latest_gaze_position

    def getPosition(self):
        """
        See getLastGazePosition().
        """
        return self.getLastGazePosition()

    def getPos(self):
        """
        See getLastGazePosition().
        """
        return self.getLastGazePosition()

    def generate_markers(self, win_size_pix):
        ''' Generate the aruco marker images based on the information provided in the excel sheet '''
        # define the aruco board
        try:
            marker_info = pd.read_excel(self._runtime_settings['aruco_info_file'], engine='openpyxl')
        except FileNotFoundError:
            print2err(MARKERS_NOT_DEFINED_MSG)
            self._aruco_info = MARKER_INFO_DEFAULT
            return

        if marker_info.empty:
            print2err(MARKERS_NOT_DEFINED_MSG)
            self._aruco_info = MARKER_INFO_DEFAULT
            return

        self._physical_screen_dimensions = self._display_device.getPhysicalDimensions()
        self._screen_size = ([self._physical_screen_dimensions['width'] * 1e-3,
                              self._physical_screen_dimensions['height'] * 1e-3])
        marker_info['size_image_cm'] = marker_info['size_cm']
        marker_info['pos_x_cm_corner'] = marker_info['pos_x_cm']
        marker_info['pos_y_cm_corner'] = marker_info['pos_y_cm']

        n = int(ARUCO_DIC.upper().split('X')[0][-1])
        marker_info['size_cm'] = [(2 + n) * size / (n + 4) for size in marker_info['size_image_cm'].values]
        # the excel sheet specifies the position of the center of each marker while the Adhawk API expects the
        # position of the bottom-left corner
        marker_info['pos_x_cm_corner'] -= marker_info['size_cm'] / 2
        marker_info['pos_y_cm_corner'] -= marker_info['size_cm'] / 2

        self._aruco_info = marker_info
        aruco_images = []
        cm2pix = lambda val: val * win_size_pix[0] / (self._physical_screen_dimensions['width'] * 1e-1)
        for _, img in marker_info.iterrows():
            size = int(cm2pix(img.size_cm))
            aruco_images.append(make_aruco_image(ARUCO_DIC, int(img.aruco_id), int(size)))

        return self._aruco_info[list(MARKER_INFO_DEFAULT.columns)].values, aruco_images

    def _initiate_screen_tracking(self):
        if self._aruco_info.empty:
            print2err(MARKERS_NOT_DEFINED_MSG)
            self._aruco_info = MARKER_INFO_DEFAULT
            return

        self._frontend_api.register_screen_board(self._screen_size[0], self._screen_size[1],
                                                 getattr(cv2.aruco, ARUCO_DIC.upper()),
                                                 self._aruco_info.aruco_id.values.astype('int'),
                                                 [list(pos) for pos in
                                                  self._aruco_info[
                                                      ['pos_x_cm_corner', 'pos_y_cm_corner', 'size_cm']].values * 1e-2],
                                                 callback=None)

    def _handle_connect(self, error):
        """The callback that is called once connection to AdHawk backend is established.
        The stream controls are set here with the user defined sampling rate and the
        self._connected bool is set to true."""
        if not error:
            if self._screen_tracking:
                self._frontend_api.set_stream_control(adhawkapi.PacketType.EXTENDED_GAZE,
                                                      self._sampling_rate, callback=(lambda *args: None))
                self._frontend_api.set_stream_control(adhawkapi.PacketType.PER_EYE_GAZE,
                                                      self._sampling_rate, callback=(lambda *args: None))
                self._frontend_api.set_stream_control(adhawkapi.PacketType.GAZE_IN_SCREEN,
                                                      self._sampling_rate, callback=(lambda *args: None))
                self._frontend_api.set_stream_control(adhawkapi.PacketType.PUPIL_DIAMETER,
                                                      self._sampling_rate, callback=(lambda *args: None))
                self._frontend_api.set_event_control(adhawkapi.EventControlBit.BLINK, 1, callback=(lambda *args: None))

            self._connected = True
        else:
            print2err(adhawkapi.errormsg(error))

    def _start_camera(self):
        # start the front facing camera
        if not self._camera_started:
            self._frontend_api.start_camera_capture(0, RESOLUTION, False, callback=self._handle_camera_start_response)
            # waiting for camera to start
            start_time = time.perf_counter()
            while not self._camera_started:
                if (time.perf_counter() - start_time) > self._max_wait_time:
                    break
                gevent.sleep(self._wait_interval_time)

    def _stop_camera(self):
        self._frontend_api.stop_camera_capture(callback=(lambda *args: None))

    def _handle_camera_start_response(self, response):
        """Handles starting the eyetracker camera"""
        self._camera_started = response == adhawkapi.AckCodes.SUCCESS
        if not self._camera_started:
            print(f'Unable to start the camera: {adhawkapi.errormsg(response)}')

    def _start_screen_tracking(self):
        if not self._camera_started:
            self._start_camera()
        self._frontend_api.start_screen_tracking(callback=(lambda *args: None))

    def _stop_screen_tracking(self):
        self._frontend_api.stop_screen_tracking(callback=(lambda *args: None))

    def _handle_gaze_data(self, timestamp, vec_x, vec_y, vec_z, vergence):
        self._latest_sample_timestamp = timestamp
        self._handleNativeEvent((EventConstants.BINOCULAR_EYE_SAMPLE, timestamp, vec_x, vec_y, vec_z, vergence,
                                 *self._latest_gaze_in_screen,
                                 *self._latest_binocular_gaze_data,
                                 *self._latest_pupil_diameter_data
                                 ))

    def _handle_binocular_gaze_data(self, _timestamp, rx, ry, rz, lx, ly, lz):
        self._latest_binocular_gaze_data[:] = [rx, ry, rz, lx, ly, lz]

    def _handle_gaze_in_screen_data(self, _timestamp, xpos, ypos):
        xpos, ypos = self._eyeTrackerToDisplayCoords((xpos, ypos))
        self._latest_gaze_in_screen[:] = [xpos, ypos]

    def _handle_pupil_diameter(self, _timestamp, right_pupil, left_pupil):
        self._latest_pupil_diameter_data[:] = [right_pupil, left_pupil]

    def _handle_events(self, event_type, timestamp, *args):
        if event_type == adhawkapi.Events.BLINK:
            duration = args[0]
            self._handleNativeEvent((EventConstants.BLINK_END, timestamp, duration))

    def _eyeTrackerToDisplayCoords(self, eyetracker_point):
        """Converts Adhawk normalized gaze-in-screen positions to the Display device coordinate space."""
        if self._display_device is None:
            return 0, 0
        gaze_x, gaze_y = eyetracker_point
        left, top, right, bottom = self._display_device.getCoordBounds()
        w, h = right - left, top - bottom
        gaze_x = w * (gaze_x - 0.5)
        gaze_y = h * (0.5 - gaze_y)
        return gaze_x, gaze_y

    def _displayToEyeTrackerCoords(self, display_x, display_y):
        """Converts a Display device point to Adhawk normalized gaze-in-screen coordinate space."""
        if self._display_device is None:
            return 0, 0
        left, top, right, bottom = self._display_device.getCoordBounds()
        w, h = right - left, top - bottom
        return (display_x + 0.5) / w, 0.5 - (display_y / h)

    def _handleNativeEvent(self, *native_event_data, **kwargs):
        if self.isReportingEvents():
            self._addNativeEventToBuffer(native_event_data[0])

    def _getIOHubEventObject(self, native_event_data):
        """The _getIOHubEventObject method is called by the ioHub Server to
        convert new native device event objects that have been received to the
        appropriate ioHub Event type representation.

        This method converts the native Adhawk gaze data events into
        an appropriate ioHub Event representation. Note that while Adhawk eye tracker provides the
        per-eye unit gaze vectors it only outputs the gaze_in_screen coordinates for the combined eye.

        Args:
            native_event_data: object or tuple of (native_event_object)

        Returns:
            tuple: The appropriate ioHub Event type in list form.

        """
        # if event is a BLINK_END event, shape accordingly
        if native_event_data[0] == EventConstants.BLINK_END:  # 58 is EventConstants.BLINK_END
            logged_time = Computer.getTime()
            event_type, timestamp, duration = native_event_data
            blink_event = [
                0,
                0,
                0,
                Device._getNextEventID(),
                event_type,
                timestamp,
                logged_time,
                logged_time,
                0,
                0,
                0,
                EyeTrackerConstants.BINOCULAR_AVERAGED,
                duration,
                0,  # status
            ]
            return blink_event

        # if event is a BINOCULAR_EYE_SAMPLE event, shape accordingly
        if native_event_data[0] == EventConstants.BINOCULAR_EYE_SAMPLE:
            logged_time = Computer.getTime()
            event_type, timestamp, vec_x, vec_y, vec_z, vergence, xpos, ypos, rx, ry, rz, lx, ly, lz, r_pupil, l_pupil = native_event_data
            gaze_angles_deg_right = np.degrees(vector_to_angles(rx, ry, rz))
            gaze_angles_deg_left = np.degrees(vector_to_angles(lx, ly, lz))

            bino_sample = [
                0,  # experiment_id, iohub fills in automatically
                0,  # session_id, iohub fills in automatically
                0,  # device_id, keep at 0
                Device._getNextEventID(),
                event_type,  # iohub event unique ID
                timestamp,
                logged_time,
                logged_time,
                0,  # confidence_interval
                0,  # delay": (logged_time - iohub_time)
                0,
                xpos,  # gaze in screen x
                ypos,  # gaze in screen y
                -vec_z,  # gaze depth in meter
                EyeTrackerConstants.UNDEFINED,  # left eye center x
                EyeTrackerConstants.UNDEFINED,  # left eye center y
                EyeTrackerConstants.UNDEFINED,  # left eye center z
                gaze_angles_deg_left[0],
                gaze_angles_deg_left[1],
                EyeTrackerConstants.UNDEFINED,  # left_raw_x
                EyeTrackerConstants.UNDEFINED,  # left_raw_y
                l_pupil,  # left_pupil_measure1
                EyeTrackerConstants.PUPIL_DIAMETER,  # left_pupil_measure1_type
                EyeTrackerConstants.UNDEFINED,  # left_pupil_measure2
                EyeTrackerConstants.UNDEFINED,  # left_pupil_measure2_type
                EyeTrackerConstants.UNDEFINED,  # left_ppd_x
                EyeTrackerConstants.UNDEFINED,  # left_ppd_y
                EyeTrackerConstants.UNDEFINED,  # left_velocity_x
                EyeTrackerConstants.UNDEFINED,  # left_velocity_y
                EyeTrackerConstants.UNDEFINED,  # left_velocity_xy
                xpos,  # gaze in screen x
                ypos,  # gaze in screen y
                vec_z,  # gaze depth
                EyeTrackerConstants.UNDEFINED,  # right eye center x
                EyeTrackerConstants.UNDEFINED,  # right eye center y
                EyeTrackerConstants.UNDEFINED,  # right eye center z
                gaze_angles_deg_right[0],
                gaze_angles_deg_right[1],
                EyeTrackerConstants.UNDEFINED,  # right_raw_x
                EyeTrackerConstants.UNDEFINED,  # right_raw_y
                r_pupil,  # right_pupil_measure1
                EyeTrackerConstants.PUPIL_DIAMETER,  # right_pupil_measure1_type
                EyeTrackerConstants.UNDEFINED,  # right_pupil_measure2
                EyeTrackerConstants.UNDEFINED,  # right_pupil_measure2_type
                EyeTrackerConstants.UNDEFINED,  # right_ppd_x
                EyeTrackerConstants.UNDEFINED,  # right_ppd_y
                EyeTrackerConstants.UNDEFINED,  # right_velocity_x
                EyeTrackerConstants.UNDEFINED,  # right_velocity_y
                EyeTrackerConstants.UNDEFINED,  # right_velocity_xy
                0,  # status
            ]
            self._latest_sample = bino_sample
            self._latest_gaze_position = [xpos, ypos]
            return bino_sample

    def _close(self):
        """Do any final cleanup of the eye tracker before the object is
        destroyed."""
        self.setRecordingState(False)
        self.setConnectionState(False)
        self.__class__._INSTANCE = None
        super()._close()
