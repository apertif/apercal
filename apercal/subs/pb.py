import numpy as np


def wsrtBeam(distance, freq):
    """
    # wsrtBeam: module to compute the apparent flux using the primary beam correction of the WSRT
    # distance: distance from the pointing centre
    # freq: frequency of the observation
    # returns: apparent flux correction factor
    """
    beamgain = (np.cos(np.deg2rad(0.068 * distance * freq * 1000.0))) ** 6.0
    return beamgain
