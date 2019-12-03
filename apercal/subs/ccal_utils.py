"""
Module with functionality to support cross-calibration
"""

# aperCC must be in the $PYTHONPATH
from aperCC.modules.Sols import BPSols
import numpy as np


def get_ratio_autocorrelation_above_limit(amp, polarisation, amp_threshold):

    # get the data that is above the threshold
    amp_above_threshold = amp[amp > amp_threshold]

    # how many data points
    n_vis_above_threshold = len(amp_above_threshold)

    # how many data points in total
    n_vis = len(amp)

    # fraction of data points above amplitude threshold
    ratio_vis_above_threshold = float(n_vis) / float(n_vis_above_threshold)

    return ratio_vis_above_threshold


# TODO: 1. Adjust the max_std (mb put to config); 2. Consider detrending...
def check_bpass_phase(bpath, max_std=3):
    """
    Check if STD of a bandpass phase lower than max_std
    Return Dict: {ANT:[XX_phase<max_std, YY_phase<max_std]}
    """
    BP = BPSols(bpath)
    res = dict()
    for ant in BP.ants:
        freq, _, phase = BP.get_ant_bpass(ant)
        std = np.nanstd(phase, axis=0)
        if not np.isfinite(std[0]) and not np.isfinite(std[1]):
            cond = np.array([True, True])  # The reference antenna
        else:
            cond = std < max_std
        res.update({ant: cond})
    return res
