"""
Module with functionality to support cross-calibration
"""

# aperCC must be in the $PYTHONPATH
# from aperCC.modules.Sols import BPSols
import numpy as np
import casacore.tables as pt
from scipy.optimize import curve_fit
import logging
from apercal.subs import misc as misc
import os
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def get_ratio_autocorrelation_above_limit(amp, amp_threshold):
    """
    Get the fraction of data that have autocorrelation amplitudes
    above a given threshold
    """

    # get the data that is above the threshold
    amp_above_threshold = amp[amp > amp_threshold]

    # how many data points
    n_vis_above_threshold = len(amp_above_threshold)

    # how many data points in total
    n_vis = len(amp)

    # fraction of data points above amplitude threshold
    ratio_vis_above_threshold = float(n_vis_above_threshold) / float(n_vis)

    return ratio_vis_above_threshold


def get_autocorr(msfile):
    """
    Gets the autocorrelation data from a dataset
    msfile: Input dataset with the autocorrelations
    """

    # get the list of channels
    # then get frequencies:
    taql_antnames = "SELECT NAME FROM {0}::ANTENNA".format(msfile)
    t = pt.taql(taql_antnames)
    ant_names = t.getcol("NAME")
    if ant_names is None:
        logger.warning(
            "Something wrong. No antenna names. Continue with next beam")

    taql_freq = "SELECT CHAN_FREQ FROM {0}::SPECTRAL_WINDOW".format(msfile)
    t = pt.taql(taql_freq)
    freqs = t.getcol('CHAN_FREQ')[0, :]

    # and number of stokes params
    taql_stokes = "SELECT abs(DATA) AS amp from {0} limit 1".format(msfile)
    t_pol = pt.taql(taql_stokes)
    pol_array = t_pol.getcol('amp')
    if pol_array is None:
        logger.warning(
            "Something wrong. No polarisation information. Continue with next beam")
    n_stokes = pol_array.shape[2]  # shape is time, one, nstokes

    # take MS file and get data
    amp_ant_array = np.empty(
        (len(ant_names), len(freqs), n_stokes), dtype=np.float32)

    # get autocorrelation
    for ant in xrange(len(ant_names)):
        try:
            taql_command = ("SELECT abs(gmeans(CORRECTED_DATA[FLAG])) AS amp "
                            "FROM {0} "
                            "WHERE ANTENNA1==ANTENNA2 && (ANTENNA1={1} || ANTENNA2={1})").format(msfile, ant)
            t = pt.taql(taql_command)
            # phase_ant_array[ant, :, :] = t.getcol('phase')[0, :, :]
            amp_ant_array[ant, :, :] = t.getcol('amp')[0, :, :]
        except Exception as e:
            amp_ant_array[ant, :, :] = np.full((len(freqs), n_stokes), np.nan)
            logger.exception(e)

    # get XX and YY
    amp_xx = amp_ant_array[:, :, 0]
    amp_yy = amp_ant_array[:, :, 3]

    return freqs, amp_xx, amp_yy


def polyfit_autocorr(autocorrdata):
    """
    Function to remove outliers from the auto-correlations, fit a polynomial of 2nd order and issue flagging of dishes dependent on covariance of the fit and the parameters of determination
    autocorrdata: Auto-correlation data in frequency, amp_xx, amp_yy order (usually from function get_autocorr)
    returns: frequency values, cleaned auto-correlation values, polynomially fitted values, covariance of the fit, parameter of determination each for XX and YY
    """
    antnames = misc.create_antnames()
    freqs = autocorrdata[0]
    XX_rclean = []
    XX_rfreq = []
    XX_rpolyvals = []
    XX_rcov = []
    XX_rr2 = []
    YY_rclean = []
    YY_rfreq = []
    YY_rpolyvals = []
    YY_rcov = []
    YY_rr2 = []
    for dish in range(0, 12):
        XX_remove = np.where(autocorrdata[1][dish] == 0.0)
        XX_clean = np.asarray(np.delete(autocorrdata[1][dish], XX_remove))
        XX_freq = np.asarray(np.delete(freqs, XX_remove))
        XX_mean = np.mean(XX_clean)
        XX_sd = np.std(XX_clean)
        XX_out = np.where((XX_clean < XX_mean - 3.0 * XX_sd)
                          | (XX_clean > XX_mean + 3.0 * XX_sd))
        XX_clean = np.delete(XX_clean, XX_out)
        XX_freq = np.delete(XX_freq, XX_out)
        try:
            XX_poly, XX_covm = np.polyfit(XX_freq, XX_clean, 2, cov=True)
            XX_polyvals = np.polyval(XX_poly, XX_freq)
            XX_polyres = np.sum((XX_clean - XX_polyvals) ** 2.0)
            XX_polytot = np.sum((XX_clean - np.mean(XX_clean)) ** 2.0)
            XX_cov = np.sqrt(np.diag(XX_covm))
            XX_r2 = 1.0 - (XX_polyres / XX_polytot)
            XX_rclean.append(XX_clean)
            XX_rfreq.append(XX_freq)
            XX_rpolyvals.append(XX_polyvals)
            XX_rcov.append(XX_cov)
            XX_rr2.append(XX_r2)
            if XX_r2 < 0.5 or XX_cov[0] >= 2e-16 or XX_cov[1] >= 1e-6 or XX_cov[2] >= 1e3:
                print 'Dish ' + str(antnames[dish]) + ' XX flagged!'
            else:
                continue
        except:
            XX_rclean.append(np.asarray(np.nan))
            XX_rfreq.append(np.asarray(np.nan))
            XX_rpolyvals.append(np.asarray(np.nan))
            XX_rcov.append(np.nan)
            XX_rr2.append(np.nan)
            print 'Dish ' + str(antnames[dish]) + ' XX flagged!'
    for dish in range(0, 12):
        YY_remove = np.where(autocorrdata[2][dish] == 0.0)
        YY_clean = np.asarray(np.delete(autocorrdata[2][dish], YY_remove))
        YY_freq = np.asarray(np.delete(freqs, YY_remove))
        YY_mean = np.mean(YY_clean)
        YY_sd = np.std(YY_clean)
        YY_out = np.where((YY_clean < YY_mean - 3.0 * YY_sd)
                          | (YY_clean > YY_mean + 3.0 * YY_sd))
        YY_clean = np.delete(YY_clean, YY_out)
        YY_freq = np.delete(YY_freq, YY_out)
        try:
            YY_poly, YY_covm = np.polyfit(YY_freq, YY_clean, 2, cov=True)
            YY_polyvals = np.polyval(YY_poly, YY_freq)
            YY_polyres = np.sum((YY_clean - YY_polyvals) ** 2.0)
            YY_polytot = np.sum((YY_clean - np.mean(YY_clean)) ** 2.0)
            YY_cov = np.sqrt(np.diag(YY_covm))
            YY_r2 = 1.0 - (YY_polyres / YY_polytot)
            YY_rclean.append(YY_clean)
            YY_rfreq.append(YY_freq)
            YY_rpolyvals.append(YY_polyvals)
            YY_rcov.append(YY_cov)
            YY_rr2.append(YY_r2)
            if YY_r2 < 0.5 or YY_cov[0] >= 2e-16 or YY_cov[1] >= 1e-6 or YY_cov[2] >= 1e3:
                print 'Dish ' + str(antnames[dish]) + ' YY flagged!'
            else:
                continue
        except:
            YY_rclean.append(np.asarray(np.nan))
            YY_rfreq.append(np.asarray(np.nan))
            YY_rpolyvals.append(np.asarray(np.nan))
            YY_rcov.append(np.nan)
            YY_rr2.append(np.nan)
            print 'Dish ' + str(antnames[dish]) + ' YY flagged!'

    return XX_rfreq, XX_rclean, XX_rpolyvals, XX_rcov, XX_rr2, YY_rfreq, YY_rclean, YY_rpolyvals, YY_rcov, YY_rr2


# TODO: 1. Adjust the max_std (mb put to config); 2. Consider detrending...
# def check_bpass_phase(bpath, max_std=3):
#     """
#     Check if STD of a bandpass phase lower than max_std
#     Return Dict: {ANT:[XX_phase<max_std, YY_phase<max_std]}
#     """
#     BP = BPSols(bpath)
#     res = dict()
#     for ant in BP.ants:
#         freq, _, phase = BP.get_ant_bpass(ant)
#         std = np.nanstd(phase, axis=0)
#         if not np.isfinite(std[0]) and not np.isfinite(std[1]):
#             cond = np.array([True, True])  # The reference antenna
#         else:
#             cond = std < max_std
#         res.update({ant: cond})
#     return res

def check_bpass_phase(bpath, max_std, plot_name=None, beam=''):
    """
    Function to check the bandpass phase solutions to identify a bad antenna.

    It checks if the standard deviation of the bandpass phase solutions is below
    a maximum standard deviation. The return is a dictionary with entries for each
    antenna and booleans for each polarisation. If the standard deviation is below
    the limit, it is True (i.e., good). If it is below, it is False (i.e., bad).

    Args:
        bpath (str): Path to bandpass file
        max_std (float): Maximum standard deviation of phase solutions

    Return
        results (dict({ant: [XX_phase<max_std, YY_phase<max_std]})): Check for each antenna and polarisaiton
    """

    # get the data from the bandpass table
    if os.path.isdir(bpath):
        taql_command = ("SELECT TIME,abs(CPARAM) AS amp, arg(CPARAM) AS phase, "
                        "FLAG FROM {0}").format(bpath)
        t = pt.taql(taql_command)
        times = t.getcol('TIME')
        amp_sols = t.getcol('amp')
        phase_sols = t.getcol('phase')
        flags = t.getcol('FLAG')
        taql_antnames = "SELECT NAME FROM {0}::ANTENNA".format(
            bpath)
        t = pt.taql(taql_antnames)
        ant_names = t.getcol("NAME")
        taql_freq = "SELECT CHAN_FREQ FROM {0}::SPECTRAL_WINDOW".format(
            bpath)
        t = pt.taql(taql_freq)
        freqs = t.getcol('CHAN_FREQ')

        # check for flags and mask
        # amp_sols[flags] = np.nan
        phase_sols[flags] = np.nan

        # time = times
        phase = phase_sols * 180./np.pi  # put into degrees
        # amp = amp_sols
        # flags = flags
        freq = freqs / 1e9  # GHz
        # t0 = get_time(times[0])
    else:
        logger.warning(
            "BP Table {} not found. Checking solutions not possible".format(bpath))
        # logger.error(error)
        # raise RuntimeError(error)

    # to store the results
    res = dict()

    # setting plot layout
    nx = 4
    ny = 3
    xsize = nx*4
    ysize = ny*4
    y_min = -180
    y_max = 180
    plt.figure(figsize=(xsize, ysize))
    plt.suptitle(
        'Bandpass phase solutions of Beam {}'.format(beam), size=30)

    # go through the antennas
    for ant in ant_names:
        a_index = ant_names.index(ant)
        freq_ant = freq[0, :]
        phase_ant = phase[a_index, :, :]
        std = np.nanstd(phase_ant, axis=0)
        logger.debug("Ant: {0}, std = {1}".format(ant, std))
        if not np.isfinite(std[0]) and not np.isfinite(std[1]):
            cond = np.array([True, True])  # The reference antenna
        else:
            cond = std < max_std
        logger.debug(
            "=> Bandpass phase solutions are good? {}".format(str(cond)))
        res.update({ant: cond})

        if plot_name is not None:
            plt.subplot(ny, nx, a_index+1)
            # plot XX
            plt.scatter(freq_ant, phase_ant[:, 0],
                        label='XX',
                        marker=',', s=1, color='C0')
            plt.scatter(freq_ant, phase_ant[:, 1],
                        label='YY',
                        marker=',', s=1, color='C1')
            plt.title('Antenna {0}'.format(ant))
            plt.ylim(y_min, y_max)
            plt.legend(markerscale=3, fontsize=14)
            plt.savefig(plot_name)

    if plot_name is not None:
        plt.close('all')

    return res
