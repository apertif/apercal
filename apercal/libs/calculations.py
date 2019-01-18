import aipy
import numpy as np

from apercal.exceptions import ApercalException
from apercal.libs import lib


def calc_scal_interval(flux, noise, obstime, baselines, nfbin, feeds, snr, cycle):
    """
    Function to automatically calculate the self-calibration solution interval for each major cycle of an observation
    flux (float): Flux in the clean model in Jy
    noise (float): Theoretical noise of the dataset
    obstime (float): Total integration time in minutes
    baselines (int): Number of available baselines
    nfbin (int): Number of frequency solution intervals
    feeds (int): Number of feeds
    snr (float): SNR for calculation. Typically 3 for phase and 10 for amplitude
    cycle (int): Major self-calibration cycle to use. Usually 1 for amplitude.
    returns (float): Solution interval to use
    """
    dof = baselines*nfbin*feeds
    noiseperdof = noise*np.sqrt(dof)
    noisesnr = snr * noiseperdof
    nsolint = flux / noisesnr
    interval = ((obstime / nsolint) / cycle)
    if interval > obstime:
        interval = obstime
    elif interval < 0.5:
        interval = 0.5
    else:
        interval = np.round(interval)
    return interval


def calc_dr_maj(drinit, dr0, majorcycles, func):
    """
    Function to calculate the dynamic range limits during major cycles
    drinit (float): The initial dynamic range
    dr0 (float): Coefficient for increasing the dynamic range threshold at each major cycle
    majorcycles (int): The number of major cycles to execute
    func (string): The function to follow for increasing the dynamic ranges. Currently 'power' is supported.
    returns (list of floats): A list of floats for the dynamic range limits within the major cycles.
    """
    if func == 'square':
        dr_maj = [drinit * np.power(dr0, m) for m in range(majorcycles)]
    else:
        raise ApercalException('Function for major cycles not supported')
    return dr_maj


def calc_theoretical_noise(dataset):
    """
    Calculate the theoretical rms of a given dataset
    dataset (string): The input dataset to calculate the theoretical rms from
    returns (float): The theoretical rms of the input dataset as a float
    """
    uv = aipy.miriad.UV(dataset)
    obsrms = lib.miriad('obsrms')
    try:
        tsys = np.median(uv['systemp'])
        if np.isnan(tsys):
            obsrms.tsys = 30.0
        else:
            obsrms.tsys = tsys
    except KeyError:
        obsrms.tsys = 30.0
    obsrms.jyperk = uv['jyperk']
    obsrms.antdiam = 25
    obsrms.freq = uv['sfreq']
    obsrms.theta = 15
    obsrms.nants = uv['nants']
    obsrms.bw = np.abs(uv['sdf'] * uv['nschan']) * 1000.0
    obsrms.inttime = 12.0 * 60.0
    obsrms.coreta = 0.88
    theorms = float(obsrms.go()[-1].split()[3]) / 1000.0
    return theorms


def calc_theoretical_noise_threshold(theoretical_noise, nsigma):
    """
    Calculates the theoretical noise threshold from the theoretical noise
    theoretical_noise (float): the theoretical noise of the observation
    returns (float): the theoretical noise threshold
    """
    theoretical_noise_threshold = (nsigma * theoretical_noise)
    return theoretical_noise_threshold


def calc_dynamic_range_threshold(imax, dynamic_range, dynamic_range_minimum):
    """
    Calculates the dynamic range threshold
    imax (float): the maximum in the input image
    dynamic_range (float): the dynamic range you want to calculate the threshold for
    returns (float): the dynamic range threshold
    """
    if dynamic_range == 0:
        dynamic_range = dynamic_range_minimum
    dynamic_range_threshold = imax / dynamic_range
    return dynamic_range_threshold


def calc_clean_cutoff(mask_threshold, c1):
    """
    Calculates the cutoff for the cleaning
    mask_threshold (float): the mask threshold to calculate the clean cutoff from
    returns (float): the clean cutoff
    """
    clean_cutoff = mask_threshold / c1
    return clean_cutoff


def calc_noise_threshold(imax, minor_cycle, major_cycle, c0):
    """
    Calculates the noise threshold
    imax (float): the maximum in the input image
    minor_cycle (int): the current minor cycle the self-calibration is in
    major_cycle (int): the current major cycle the self-calibration is in
    returns (float): the noise threshold
    """
    noise_threshold = imax / ((c0 + minor_cycle * c0) * (major_cycle + 1))
    return noise_threshold


def calc_mask_threshold(theoretical_noise_threshold, noise_threshold, dynamic_range_threshold):
    """
    Function to calculate the actual mask_threshold and the type of mask threshold from the
    theoretical noise threshold, noise threshold, and the dynamic range threshold
    theoretical_noise_threshold (float): The theoretical noise threshold calculated by
                                         calc_theoretical_noise_threshold
    noise_threshold (float): The noise threshold calculated by calc_noise_threshold
    dynamic_range_threshold (float): The dynamic range threshold calculated by calc_dynamic_range_threshold
    returns (float, string): The maximum of the three thresholds, the type of the maximum threshold
    """
    # if np.isinf(dynamic_range_threshold) or np.isnan(dynamic_range_threshold):
    #     dynamic_range_threshold = noise_threshold
    mask_threshold = np.max([theoretical_noise_threshold, noise_threshold, dynamic_range_threshold])
    mask_argmax = np.argmax([theoretical_noise_threshold, noise_threshold, dynamic_range_threshold])
    if mask_argmax == 0:
        mask_threshold_type = 'Theoretical noise threshold'
    elif mask_argmax == 1:
        mask_threshold_type = 'Noise threshold'
    elif mask_argmax == 2:
        mask_threshold_type = 'Dynamic range threshold'
    else:
        raise ApercalException("Unknown mask thresholdtype")

    return mask_threshold, mask_threshold_type


def get_freqstart(dataset, startchan):
    """
    dataset: The dataset to get the first frequency from
    returns: The starting frequency of the observation
    """
    uv = aipy.miriad.UV(dataset)
    startfreq = (uv['freq'] + int(startchan) * uv['sdf']) * 1E9
    return startfreq


def calc_dr_min(dr_maj, majc, minorcycles, function):
    """
    Function to calculate the dynamic range limits during minor cycles
    dr_maj (list of floats): List with dynamic range limits for major cycles. Usually from calc_dr_maj
    majc (int): The major cycles you want to calculate the minor cycle dynamic ranges for
    minorcycles (int): The number of minor cycles to use
    function (string): The function to follow for increasing the dynamic ranges. Currently 'square', 'power', and
                       'linear' is supported.
    returns (list of floats): A list of floats for the dynamic range limits within the minor cycles.
    """
    if majc == 0:  # Take care about the first major cycle
        prevdr = 0
    else:
        prevdr = dr_maj[majc - 1]
    # The different options to increase the minor cycle threshold
    if function == 'square':
        dr_min = [prevdr + ((dr_maj[majc] - prevdr) * (n ** 2.0)) / ((minorcycles - 1) ** 2.0) for n in
                  range(minorcycles)]
    elif function == 'power':
        # Not exactly need to work on this, but close
        dr_min = [prevdr + np.power((dr_maj[majc] - prevdr), (1.0 / n)) for n in range(minorcycles)][::-1]
    elif function == 'linear':
        dr_min = [(prevdr + ((dr_maj[majc] - prevdr) / (minorcycles - 1)) * n) for n in range(minorcycles)]
    else:
        raise ApercalException(' Function for minor cycles not supported!')
    return dr_min


def calc_line_masklevel(miniter, dr0, maxdr, minorcycle0_dr, imax):
    if miniter == 0:
        really = False
        masklevels = 1
    else:
        really = True
        drlevels = [np.power(dr0, n + 1) for n in range(miniter)]
        drlevels[-1] = maxdr
        if drlevels[0] >= minorcycle0_dr:
            drlevels[0] = minorcycle0_dr
        else:
            pass
        masklevels = imax / drlevels
    return really, masklevels


def calc_miniter(maxdr, dr0):
    """
    Calculate the number of minor cycles needed for cleaning a line channel
    maxdr (float): The maximum dynamic range reachable calculated by the theoretical noise and maximum pixel value
                   in the image
    dr0 (float): The increase for each cycle to clean deeper
    returns (int): Number of minor cycle iterations for cleaning
    """
    nminiter = int(np.ceil(np.log(maxdr) / np.log(dr0)))
    return nminiter
