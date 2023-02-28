#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simple iohub eye tracker device demo.
Select which tracker to use by setting the TRACKER variable below.
"""

from psychopy import core, visual
from psychopy.iohub import launchHubServer
from psychopy.iohub.util import hideWindow, showWindow

# Eye tracker to use ('mouse', 'eyelink', 'gazepoint', 'tobii', or 'adhawk')
TRACKER = 'mouse'
BACKGROUND_COLOR = [128, 128, 128]

# if chosen eyetracker is adhawk, define ARUCO_INFO_LOCATION with the path to your aruco_info.xlsx file
ARUCO_INFO_LOCATION = 'C:/insert_your_path_here/aruco_info.xlsx'
# PsychoPy monitor name (accessible in the builder Monitor Center). Monitor size and resolution needs to be defined
# correctly when using screen tracking with Adhawk Eye Tracker
MONITOR_NAME = '55w_60dist'


devices_config = dict()
eyetracker_config = dict(name='tracker')
if TRACKER == 'mouse':
    eyetracker_config['calibration'] = dict(screen_background_color=BACKGROUND_COLOR)
    devices_config['eyetracker.hw.mouse.EyeTracker'] = eyetracker_config
elif TRACKER == 'eyelink':
    eyetracker_config['model_name'] = 'EYELINK 1000 DESKTOP'
    eyetracker_config['runtime_settings'] = dict(sampling_rate=1000, track_eyes='RIGHT')
    eyetracker_config['calibration'] = dict(screen_background_color=BACKGROUND_COLOR)
    devices_config['eyetracker.hw.sr_research.eyelink.EyeTracker'] = eyetracker_config
elif TRACKER == 'gazepoint':
    eyetracker_config['calibration'] = dict(use_builtin=False, screen_background_color=BACKGROUND_COLOR)
    devices_config['eyetracker.hw.gazepoint.gp3.EyeTracker'] = eyetracker_config
elif TRACKER == 'tobii':
    eyetracker_config['calibration'] = dict(screen_background_color=BACKGROUND_COLOR)
    devices_config['eyetracker.hw.tobii.EyeTracker'] = eyetracker_config
elif TRACKER == 'adhawk':
    eyetracker_config['runtime_settings'] = dict(sampling_rate=125,
                                                 calibration_sampling_duration=500,
                                                 enable_screen_tracking=True,
                                                 aruco_info_file=ARUCO_INFO_LOCATION)
    devices_config['eyetracker.hw.adhawk.EyeTracker'] = eyetracker_config
else:
    print("{} is not a valid TRACKER name; please use 'mouse', 'eyelink', 'gazepoint', 'tobii', or 'adhawk'.".format(TRACKER))
    core.quit()

# Number if 'trials' to run in demo
TRIAL_COUNT = 2
# Maximum trial time / time timeout
T_MAX = 60.0
win = visual.Window((1920, 1080),
                    units='pix',
                    fullscr=True,
                    allowGUI=False,
                    colorSpace='rgb255',
                    monitor=MONITOR_NAME,
                    color=BACKGROUND_COLOR
                    )

win.setMouseVisible(False)
text_stim = visual.TextStim(win, text="Start of Experiment",
                            pos=[0, 0], height=24,
                            color='black', units='pix', colorSpace='named',
                            wrapWidth=win.size[0] * .9)

text_stim.draw()
win.flip()

io = launchHubServer(window=win, **devices_config)

# Get some iohub devices for future access.
keyboard = io.getDevice('keyboard')
tracker = io.getDevice('tracker')

if TRACKER == 'adhawk':
    ##### screen tracking code ######
    aruco_markers = []
    markers_info = tracker.generate_markers(win_size_pix=win.size)
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
        ''' Draw the aruco markers in the screen. Given a target xy position
        it will ignore any marker that intersects with that point in the screen '''
        if not eyetracker_config['enable_screen_tracking']:
            return
        for marker in aruco_markers:
            xin = yin = False
            if target_pos is not None:
                xin = (marker.pos[0] - marker.size[0]/2) <= target_pos[0] <= (marker.pos[0] + marker.size[0]/2)
                yin = (marker.pos[1] - marker.size[1]/2) <= target_pos[1] <= (marker.pos[1] + marker.size[1]/2)
            if not (xin and yin):
                marker.draw()
    ##################################

# Minimize the PsychoPy window if needed
hideWindow(win)
# Display calibration gfx window and run calibration.
result = tracker.runSetupProcedure()
print("Calibration returned: ", result)
if not result:
    win.close()
    tracker.setConnectionState(False)
    core.quit()

# Maximize the PsychoPy window if needed
showWindow(win)

gaze_ok_region = visual.Circle(win, lineColor='black', radius=300, units='pix', colorSpace='named')

gaze_dot = visual.GratingStim(win, tex=None, mask='gauss', pos=(0, 0),
                              size=(40, 40), color='green', colorSpace='named', units='pix')

text_stim_str = 'Eye Position: %.2f, %.2f. In Region: %s\n'
text_stim_str += 'Press space key to start next trial.'
missing_gpos_str = 'Eye Position: MISSING. In Region: No\n'
missing_gpos_str += 'Press space key to start next trial.'
text_stim.setText(text_stim_str)

# Run Trials.....
t = 0
while t < TRIAL_COUNT:
    io.clearEvents()
    tracker.setRecordingState(True)
    run_trial = True
    tstart_time = core.getTime()
    while run_trial is True:
        if TRACKER == 'adhawk':
            draw_markers()
        # Get the latest gaze position in display coord space.
        gpos = tracker.getLastGazePosition()
        # Update stim based on gaze position
        valid_gaze_pos = isinstance(gpos, (tuple, list))
        gaze_in_region = valid_gaze_pos and gaze_ok_region.contains(gpos)
        if valid_gaze_pos:
            # If we have a gaze position from the tracker, update gc stim and text stim.
            if gaze_in_region:
                gaze_in_region = 'Yes'
            else:
                gaze_in_region = 'No'
            text_stim.text = text_stim_str % (gpos[0], gpos[1], gaze_in_region)

            gaze_dot.setPos(gpos)
        else:
            # Otherwise just update text stim
            text_stim.text = missing_gpos_str

        # Redraw stim
        gaze_ok_region.draw()
        text_stim.draw()
        if valid_gaze_pos:
            gaze_dot.draw()

        # Display updated stim on screen.
        flip_time = win.flip()

        # Check any new keyboard char events for a space key.
        # If one is found, set the trial end variable.
        #
        if keyboard.getPresses(keys=' '):
            run_trial = False
        elif keyboard.getPresses(keys='escape'):
            core.quit()
        elif core.getTime()-tstart_time > T_MAX:
            run_trial = False
    win.flip()
    # Current Trial is Done
    # Stop eye data recording
    tracker.setRecordingState(False)
    t += 1

# All Trials are done
# End experiment
win.close()
tracker.setConnectionState(False)
core.quit()
