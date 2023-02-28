''' Some helper functions used by the Adhawk eyetracker class in iohub'''
import enum

import cv2
import cv2.aruco
import numpy as np


class EulerRotationOrder(enum.IntEnum):
    '''Various Euler rotation orders. lowercase x,y, z stand for the axes of the world coordinate system, and
    uppercase X, Y, and Z stands for the local moving axes'''
    # pylint: disable=invalid-name
    XY = 0  # first rotate around local X, then rotate around local Y axis (this is also known as yx')
    YX = 1  # first rotate around local Y, then rotate around local X axis (this is also known as xy')


def vector_to_angles(xpos, ypos, zpos, rotation_order: EulerRotationOrder = EulerRotationOrder.XY):
    '''
    Converts a gaze vector to [azimuth (yaw), elevation (pitch)] angles based on a specific rotation order and
    a vector defined in our usual backend coordinate system (with X oriented in the positive direction to the right,
    Y oriented in the positive direction going up and Z oriented in the positive direction behind the user). Also note
    that we want the positive yaw to be rotation to the right.
    '''
    azimuth = elevation = np.nan
    if rotation_order == EulerRotationOrder.YX:
        azimuth = np.arctan2(xpos, -zpos)
        elevation = np.arctan2(ypos, np.sqrt(xpos ** 2 + zpos ** 2))
    elif rotation_order == EulerRotationOrder.XY:
        azimuth = np.arctan2(xpos, np.sqrt(ypos ** 2 + zpos ** 2))
        elevation = np.arctan2(ypos, -zpos)
    return azimuth, elevation


def vectors_to_angles(vectors, rotation_order: EulerRotationOrder = EulerRotationOrder.XY):
    ''' convert given direction vectors to azimuth, elevation'''
    outputs = np.zeros((vectors.shape[0], 2), dtype=np.float64)
    for i in range(vectors.shape[0]):
        outputs[i] = np.array(vector_to_angles(*vectors[i], rotation_order=rotation_order))
    return outputs


def make_aruco_image(aruco_dic: str, aruco_id: int, marker_size_pixels: int):
    border_gray_level = 255
    aruco_square = np.zeros((marker_size_pixels, marker_size_pixels), dtype=np.uint8)
    aruco_square = cv2.aruco.drawMarker(cv2.aruco.Dictionary_get(getattr(cv2.aruco, aruco_dic.upper())),
                                        aruco_id, marker_size_pixels, aruco_square, 1)

    n = int(aruco_dic.upper().split('X')[0][-1])
    border_size = int(marker_size_pixels / (n+2))
    image_size = int(marker_size_pixels + 2 * border_size)
    marker_image = np.ones((image_size, image_size), dtype=np.uint8) * border_gray_level
    marker_image[border_size:border_size + marker_size_pixels, border_size:border_size + marker_size_pixels] = \
        aruco_square
    marker_image = np.stack((marker_image,)*3, axis=-1) / 255
    return np.flipud(marker_image)
