###################
AdHawk Microsystems
###################

.. contents:: Table of Contents

*******************************************
AdHawk MindLink High Level Introduction
*******************************************

The AdHawk Microsystems `MindLink <https://www.adhawkmicrosystems.com/adhawk-mindlink>`__ is a lightweight, wearable eye tracker that uses micro-electromechanical systems (MEMS) to track user's eye movements.

Remote eye trackers capture user's eye movements from a distance and provide gaze estimates in the computer coordinate system. Unlike these systems, the AdHawk MindLink eye tracker is head-mounted, making it suitable for all-day recording in real-world scenarios, with the user moving freely within their environment.

The AdHawk Mindlink provides an estimate of the user's gaze in 3D as well as a 2D estimation in its front-facing camera image. AdHawk Mindlink eye tracking software also provides gaze estimation in screen coordinates system with the help of fiducial markers that are displayed on the screen and tracked in the user's field of view.

.. image:: https://github.com/psychopy/psychopy/blob/dev/psychopy/iohub/devices/eyetracker/hw/adhawk/documentation_images/adHawk_glasses.png
    :width: 700px
    :align: center
    :alt: AdHawk MindLink wearable eye tracking glasses


**************************************
Device, Software, and Initial Setup
**************************************

Additional Software Requirements
================================

Download the AdHawk Backend software.

Download the AdHawk Microsystems Python SDK

- Install the python SDK via pip by running the following line in the command line (terminal):
   ``pip install adhawk``
- Alternatively you can download the source from https://pypi.org/project/adhawk/ and install manually.

Supported Platforms
===================

AdHawk MindLink glasses support:

-   Windows
-   Linux
-   Mac

Setting Up the Eye Tracker
==========================

1. Follow `AdHawk Setup Guide <https://www.adhawkmicrosystems.com/user_guide#setup>`__
   for initial setup.

2. Once initial setup is completed, `launch AdHawk Backend
   <https://www.adhawkmicrosystems.com/user_guide#backend-service>`__ to allow
   eye tracking to begin once requested. The AdHawk Backend will need to be running
   any time a |PsychoPy| experiment is run with eye tracking using AdHawk MindLink Glasses.

Setting Up the Experiment in |PsychoPy| Builder
=====================

1. Open ``experiment settings`` in the Builder Window (cog icon in top
   panel)
2. Open the ``Eye tracking`` tab
3. Modify the properties as follows:

-   Select ``AdHawk Microsystems`` from the ``Eye tracker Device`` drop down menu.
-   ``Sampling Rate`` - Gaze data sampling rate to be used for the experiment. Supported options are 60 Hz, 125 Hz, 250 Hz, and 500 Hz.
-   ``Calibration sampling duration (ms)`` - Sampling duration, in milliseconds, for each calibration point in the calibration routine. Supported range is 100 ms to 1000 ms.
-   ``Enable Screen Tracking`` - Enable or disable screen tracking with this checkbox setting. If the box is unchecked, screen tracking is disabled, meaning no ArUco markers will
    be displayed during the experiment and only per-eye gaze angles and pupil diameter will be logged in the ``BinocularEyeSampleEvents``. If the box is checked, screen tracking is enabled, meaning ArUco markers will be displayed in the experiment and gaze-in-screen data will be included in the ``BinocularEyeSampleEvents``. To set up screen tracking for AdHawk MindLink, see the `Setting Up Screen Tracking
    <https://psychopy.org/api/iohub/device/eyetracker_interface/AdHawk_Microsystems_Implementation_Notes.html#setting-up-screen-tracking>`__ section below.
-   ``ArUco Info File`` - The file location of a spreadsheet specifying the visual markers that should be displayed on the screen for screen tracking. Each row in the Excel sheet contains the index of the ArUco marker, position of the center of the marker, and size of the marker. This field only needs to be filled if screen tracking is enabled.
4. In the ``Data`` tab, check the ``Save hdf5 file`` option to make sure eye tracking data get logged.

.. image:: https://github.com/psychopy/psychopy/blob/dev/psychopy/iohub/devices/eyetracker/hw/adhawk/documentation_images//psychopy_eyetracking_tab.png
    :width: 700px
    :align: center
    :alt: Experiment settings ``eye tracking`` tab for AdHawk Microsystems

Setting Up Screen Tracking
========================

To enable gaze-in-screen data, AdHawk screen tracking needs to be set up. Note that eye tracking experiments should run
in full-screen mode and ArUco marker positions are based on the experiment being in full-screen mode. Full-screen mode
can be enabled via ``experiment settings`` in the ``Screen`` tab by checking the ``Full-screen window`` field.

The below steps describe the screen tracking setup process.

1. In ``experiment settings``, open the ``Eye tracking`` tab, and select ``AdHawk Microsystems`` from the ``Eye tracker Device`` dropdown. Check the ``Enable screen tracking`` box and enter the location of the Excel sheet (.xlsx file) in the ``ArUco Info File`` field.
The Excel sheet should be defined as follows:

-   The first row should define the header for 4 columns: ``aruco_id``, ``pos_x_cm``, ``pos_y_cm``, ``size_cm``. Those details should be defined in the following rows of the spreadsheet per marker to display on the screen.

      - ``aruco_id``: index of the ArUco marker which is an integer number from 0 to 50.
      - ``pos_x_cm``: x position of the center of the marker relative to the AdHawk screen coordinate system located at the top-left corner of the display (in cm)
      - ``pos_y_cm``: y position of the center of the marker relative to the AdHawk screen coordinate system located at the top-left corner of the display (in cm)
      - ``size_cm``: size of the marker image (marker plus a white border around it) in cm

-   Define at least two markers for screen tracking and place them at the corners of the screen. Four markers, one at each corner of the screen, is recommended for stable screen tracking.

.. list-table:: Example ArUco info spreadsheet for 30cm wide screen
    :widths: 25 25 50
    :header-rows: 1

    * - aruco_id
      - pos_x_cm
      - pos_y_cm
      - size_cm
    * - 0
      - 2
      - -2
      - 4
    * - 1
      - 28
      - -2
      - 4
    * - 2
      - 2
      - -15
      - 4
    * - 3
      - 28
      - -15
      - 4

.. image:: https://github.com/psychopy/psychopy/blob/dev/psychopy/iohub/devices/eyetracker/hw/adhawk/documentation_images/screen_tracking_virtual_example.png
    :width: 700px
    :align: center
    :alt: Monitor with ArUco markers defined in screen space for AdHawk screen tracking.

2. In one of the code components, add the following code in the ``Begin Experiment`` tab::

        aruco_markers = []
        markers_info = eyetracker.generate_markers(win_size_pix=win.size)
        if markers_info is not None:
            aruco_info, aruco_images = markers_info
            cm2pix = lambda val: val * win.size[0] / win.monitor.getWidth()
            for i, (aruco_id, pos_x, pos_y, size) in enumerate(aruco_info):
                size = cm2pix(size)
                pos = [-win.size[0] / 2 + cm2pix(pos_x),
                        win.size[1] / 2 + cm2pix(pos_y)]
                aruco_markers.append(visual.ImageStim(win,
                                                       image=aruco_images[i],
                                                       units='pix',
                                                       pos=pos,
                                                       size=size
                                                       ))
        def draw_markers(target_pos=None):
            ''' Draw the ArUco markers in the screen. Given a target xy position
            it will ignore any marker that intersects with that point in the screen '''
            if not ioConfig['eyetracker.hw.adhawk.EyeTracker']['runtime_settings']['enable_screen_tracking']:
                return
            for marker in aruco_markers:
                xin = yin = False
                if target_pos is not None:
                    xin = (marker.pos[0] - marker.size[0]/2) <= target_pos[0] <= (marker.pos[0] + marker.size[0]/2)
                    yin = (marker.pos[1] - marker.size[1]/2) <= target_pos[1] <= (marker.pos[1] + marker.size[1]/2)
                if not (xin and yin):
                    marker.draw()

3. Add a code component to any routine that uses screen tracking. In all of these code components, add the
   following code in the ``Each Frame`` tab::

    draw_markers()

4. Add a monitor to the |PsychoPy| ``monitor center`` and fill in the ``Size`` and ``Screen Width`` fields. Save the changes.
5. In ``experiment settings``, open the ``Screen`` tab. Enter the created monitor name in the ``Monitor`` field and the monitor index in the ``Screen`` field.

If an eye tracker validation routine is in the experiment, an extra step of modifying the experiment code is required. Once the experiment is fully defined in |PsychoPy| Builder, compile the experiment into python code, open the code in |PsychoPy| Coder, and make the following change in the file:

-   search for ``validation = iohub.ValidationProcedure`` in the file and pass the extra argument of ``custom_draw_callback=draw_markers`` to that function.

Any time the experiment is re-compiled from |PsychoPy| Builder, the above step will need to be repeated for validation functionality.

*******************************
Implementation and API Overview
*******************************

Eye Tracker Class
================

.. autoclass:: psychopy.iohub.devices.eyetracker.hw.adhawk.EyeTracker
    :members: trackerTime, trackerSec, setConnectionState, isConnected,
        runSetupProcedure, setRecordingState, isRecordingEnabled, getLastSample,
        getLastGazePosition
    :undoc-members:
    :show-inheritance:

Supported Event Types
=====================

The AdHawk Microsystems integration into |PsychoPy| provides real-time access to binocular
sample data. All gaze events will be emitted as
:py:class:`BinocularEyeSampleEvents <psychopy.iohub.devices.eyetracker.BinocularEyeSampleEvent>`
events. In addition, :py:class:`BlinkEndEvents <psychopy.iohub.devices.eyetracker.BlinkEndEvents>`
are supported to provide blink data.

The supported fields are described below.

.. autoclass:: psychopy.iohub.devices.eyetracker.BinocularEyeSampleEvent

    .. attribute:: device_time
        :type: float

        Time of gaze measurement.

    .. attribute:: logged_time
        :type: float

        Time at which the sample was received in PsychoPy, in sec.msec format, using
        PsychoPy clock.

    .. attribute:: time
        :type: float

        Time at which the sample was received in Psychopy, in sec.msec format, using
        PsychoPy clock.

    .. attribute:: confidence_interval
        :type: float
        :value: -1.0

        Currently not supported, always set to ``0``.

    .. attribute:: delay
        :type: float

        Currently not supported, always set to ``0``.

    .. attribute:: left_gaze_x
        :type: float

        X component of gaze location in display coordinates. Same as ``right_gaze_x``.

    .. attribute:: left_gaze_y
        :type: float

        Y component of gaze location in display coordinates. Same as ``right_gaze_y``.

    .. attribute:: left_gaze_z
        :type: float
        :value: 0 or float("nan")

        Z component of gaze location in display coordinates. Set to ``0.0``.
        Same as ``right_gaze_z``.

    .. attribute:: left_eye_cam_x
        :type: float

        X component of 3D eye model location in undistorted eye camera coordinates.
        Currently not supported.

    .. attribute:: left_eye_cam_y
        :type: float

        Y component of 3D eye model location in undistorted eye camera coordinates.
        Currently not supported.

    .. attribute:: left_eye_cam_z
        :type: float

        Z component of 3D eye model location in undistorted eye camera coordinates.
        Currently not supported.

    .. attribute:: left_angle_x
        :type: float

        The azimuth (yaw) angle of the left eye.

    .. attribute:: left_angle_y
        :type: float

        The elevation (pitch) angle of the left eye.

    .. attribute:: left_raw_x
        :type: float

        Currently not supported.

    .. attribute:: left_raw_y
        :type: float

        Currently not supported.

    .. attribute:: left_pupil_measure1
        :type: float

        The diameter of the left pupil.

    .. attribute:: left_pupil_measure1_type
        :type: int
        :value: psychopy.iohub.constants.EyeTrackerConstants.PUPIL_DIAMETER

        The type of left pupil measurement1. This is a relative measure of pupil size and is uncalibrated.

    .. attribute:: left_pupil_measure2
        :type: Optional[float]

        Currently not supported.

    .. attribute:: pupil_measure2_type
        :type: int

        Currently not supported.

    .. attribute:: right_gaze_x
        :type: float

        X component of gaze location in display coordinates. Same as ``left_gaze_x``.

    .. attribute:: right_gaze_y
        :type: float

        Y component of gaze location in display coordinates. Same as ``left_gaze_y``.

    .. attribute:: right_gaze_z
        :type: float
        :value: 0 or float("nan")

        Z component of gaze location in display coordinates. Set to ``0.0``.
        Same as ``left_gaze_z``.

    .. attribute:: right_eye_cam_x
        :type: float

        X component of 3D eye model location in undistorted eye camera coordinates.
        Currently not supported.

    .. attribute:: right_eye_cam_y
        :type: float

        y component of 3D eye model location in undistorted eye camera coordinates.
        Currently not supported.

    .. attribute:: right_eye_cam_z
        :type: float

        Z component of 3D eye model location in undistorted eye camera coordinates.
        Currently not supported.

    .. attribute:: right_angle_x
        :type: float

        The azimuth (yaw) angle of the left eye.

    .. attribute:: right_angle_y
        :type: float

        The elevation (pitch) angle of the left eye.

    .. attribute:: right_raw_x
        :type: float

        Currently not supported.

    .. attribute:: right_raw_y
        :type: float

        Currently not supported.

    .. attribute:: right_pupil_measure1
        :type: float

        The diameter of the right pupil.

    .. attribute:: right_pupil_measure1_type
        :type: int
        :value: psychopy.iohub.constants.EyeTrackerConstants.PUPIL_DIAMETER

        The type of right pupil measurement1. This is a relative measure of pupil size and is uncalibrated.

    .. attribute:: right_pupil_measure2
        :type: Optional[float]

        Currently not supported.

    .. attribute:: right_pupil_measure2_type
        :type: int

        Currently not supported.

.. autoclass:: psychopy.iohub.devices.eyetracker.BlinkEndEvent

    .. attribute:: device_time
        :type: float

        Time of gaze measurement.

    .. attribute:: logged_time
        :type: float

        Time at which the sample was received in PsychoPy, in sec.msec format, usin PsychoPy clock.

    .. attribute:: time
        :type: float

        Time at which the sample was received in Psychopy, in sec.msec format, using PsychoPy clock.

    .. attribute:: confidence_interval
        :type: float
        :value: -1.0

        Currently not supported, always set to ``0``.

    .. attribute:: delay
        :type: float

        Currently not supported, always set to ``0``.

    .. attribute:: event_type
        :type: int
        :value: EyeTracker.Constants.BINOCULAR_AVERAGED

        The eye event type of the blink event.

    .. attribute:: duration
        :type: float

        The duration of the blink event.

Default Device Settings
-----------------------
.. literalinclude:: ../default_yaml_configs/default_adhawk_eyetracker.yaml
    :language: yaml


**Last Updated:** October, 2022
