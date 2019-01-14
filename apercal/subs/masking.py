import os
import logging
import numpy as np
import bdsf
import astropy.io.fits as pyfits

from apercal.libs import lib
from apercal.subs import imstats
from apercal.subs import managefiles
from apercal.subs import convim
from apercal.subs import qa
from apercal.exceptions import ApercalException

logger = logging.getLogger(__name__)


def calc_dr_maj(drinit, dr0, majorcycles, function_):
    """
    Function to calculate the dynamic range limits during major cycles for phase self-calibration
    drinit (float): The initial dynamic range
    dr0 (float): Coefficient for increasing the dynamic range threshold at each major cycle
    majorcycles (int): The number of major cycles to execute
    function_ (string): The function to follow for increasing the dynamic ranges. Currently 'power' is supported.
    returns (list of floats): A list of floats for the dynamic range limits within the major cycles.
    """
    if function_ == 'power':
        dr_maj = [drinit * np.power(dr0, m) for m in range(majorcycles)]
    else:
        raise ApercalException('Function for major cycles not supported')
    return dr_maj


def calc_dr_min(dr_maj, majc, minorcycles, mindr, function_):
    """
    Function to calculate the dynamic range limits during minor cycles for phase self-calibration
    dr_maj (list of floats): List with dynamic range limits for major cycles. Usually from calc_dr_maj
    majc (int): The major cycles you want to calculate the minor cycle dynamic ranges for
    minorcycles (int): The number of minor cycles to use
    function_ (string): The function to follow for increasing the dynamic ranges. Currently 'square', 'power', and
                       'linear' is supported.
    returns (list of floats): A list of floats for the dynamic range limits within the minor cycles.
    """
    if majc == 0:  # Take care about the first major cycle
        prevdr = 0
    else:
        prevdr = dr_maj[majc - 1]
    # The different options to increase the minor cycle threshold
    if function_ == 'square':
        dr_min = [prevdr + ((dr_maj[majc] - prevdr) * (n ** 2.0)) / ((minorcycles - 1) ** 2.0) for n in
                  range(minorcycles)]
    elif function_ == 'power':
        dr_min = [prevdr + np.power((dr_maj[majc] - prevdr), (1.0 / n)) for n in range(minorcycles)][
                 ::-1]  # Not exactly need to work on this, but close
    elif function_ == 'linear':
        dr_min = [(prevdr + ((dr_maj[majc] - prevdr) / (minorcycles - 1)) * n) for n in range(minorcycles)]
    else:
        raise ApercalException('Function for minor cycles not supported! Exiting!')
    if dr_min[0] == 0:
        dr_min[0] = mindr
    elif np.isnan(dr_min[0]):
        dr_min[0] = mindr
    else:
        pass
    return dr_min


def calc_dr_amp(drstart, dr0, minorcycles, function_):
    """
    Function to calculate the dynamci range limits during the amplitude self-calibration
    drstart (float): Dynamic range of the last phase calibration mask
    dr0 (float): Coefficient for increasing the dynamic range threshold at each major cycle
    minorcycles (int): Number of maximum minor cycles during cleaning for amplitude calibration
    function_ (string): The function to follow for increasing the dynamic ranges. Currently 'square', 'power', and 'linear' is supported.
    returns (list of floats): A list of floats for the dynamic range limits within the minor cycles.
    """
    dr_limits = [drstart * np.power(dr0, m) for m in range(2)]
    dr_start = dr_limits[0]
    dr_end = dr_limits[1]
    # The different options to increase the minor cycle threshold
    if function_ == 'square':
        dr_min = [dr_start + ((dr_end - dr_start) * (n ** 2.0)) / ((minorcycles - 1) ** 2.0) for n in
                  range(minorcycles)]
    elif function_ == 'power':
        dr_min = [dr_start + np.power((dr_end - dr_start), (1.0 / n)) for n in range(minorcycles)][
                 ::-1]  # Not exactly need to work on this, but close
    elif function_ == 'linear':
        dr_min = [(dr_start + ((dr_end - dr_start) / (minorcycles - 1)) * n) for n in range(minorcycles)]
    else:
        raise ApercalException(' Function for minor cycles not supported! Exiting!')
    return dr_min


def get_theoretical_noise(self, dataset):
    """
    Subroutine to create a Stokes V image from a dataset and measure the noise, which should be similar to the theoretical one
    image (string): The path to the dataset file.
    returns (numpy array): The rms of the image
    """
    invert = lib.miriad('invert')
    invert.vis = dataset
    invert.map = 'vrms'
    invert.beam = 'vbeam'
    invert.imsize = 1024
    invert.cell = 5
    invert.stokes = 'v'
    invert.slop = 1
    invert.robust = -2
    invert.options='mfs'
    invert.go()
    vmax, vmin, vstd = imstats.getimagestats(self, 'vrms')
    gaussianity = qa.checkimagegaussianity(self, 'vrms', 1e-03)
    if os.path.isdir('vrms') and os.path.isdir('vbeam'):
        managefiles.director(self, 'rm', 'vrms')
        managefiles.director(self, 'rm', 'vbeam')
    else:
        raise ApercalException('Stokes V image was not created successfully. Cannot calculate theoretical noise! No iterative selfcal possible!')
    return gaussianity, vstd


def calc_theoretical_noise_dr(imax, theoretical_noise, nsigma):
    """
    Calculates the theoretical noise dynamic range
    theoretical_noise (float): the theoretical noise of the observation
    returns (float): the theoretical noise dynamic range
    """
    theoretical_noise_dr = imax / (nsigma * theoretical_noise)
    return theoretical_noise_dr


def calc_dynamic_range_dr(minor_cycle_list, minor_cycle, dynamic_range_minimum):
    """
    Calculates the dynamic range hreshold
    imax (float): the maximum in the input image
    dynamic_range (float): the dynamic range you want to calculate the threshold for
    returns (float): the dynamic range threshold
    """
    dynamic_range_dr = minor_cycle_list[minor_cycle]
    if dynamic_range_dr == 0:
        dynamic_range_dr = dynamic_range_minimum
    return dynamic_range_dr


def calc_noise_dr(minor_cycle, major_cycle, c0):
    """
    Calculates the noise dynamic range
    minor_cycle (int): the current minor cycle the self-calibration is in
    major_cycle (int): the current major cycle the self-calibration is in
    returns (float): the noise dynamic range
    """
    noise_dr = ((c0 + minor_cycle * c0) * (major_cycle + 1))
    return noise_dr


def calc_theoretical_noise_threshold(imax, theoretical_noise_dr):
    """
    Calculates the theoretical noise threshold from the theoretical noise dynamic range
    imax (float): the maximum of the dirty image
    theoretical_noise_dr (float): the theoretical noise dynamic range
    returns (float): the theoretical noise threshold
    """
    theoretical_noise_threshold = imax / theoretical_noise_dr
    return theoretical_noise_threshold


def calc_dynamic_range_threshold(imax, dynamic_range_dr):
    """
    Calculates the dynamic range threshold
    imax (float): the maximum in the input image
    dynamic_range_dr (float): the dynamic range you want to calculate the threshold for
    returns (float): the dynamic range threshold
    """
    dynamic_range_threshold = imax / dynamic_range_dr
    return dynamic_range_threshold


def calc_noise_threshold(imax, noise_dr):
    """
    Calculates the noise threshold
    imax (float): the maximum in the input image
    noise_dr (float): the noise dynamic range to calculate the threshold for
    returns (float): the noise threshold
    """
    noise_threshold = imax / noise_dr
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
        mask_threshold_type = 'TN'
    elif mask_argmax == 1:
        mask_threshold_type = 'NT'
    elif mask_argmax == 2:
        mask_threshold_type = 'DR'
    else:
        raise ApercalException("Unknown mask thresholdtype")

    return mask_threshold, mask_threshold_type


def calc_clean_cutoff(mask_threshold, c1):
    """
    Calculates the cutoff for the cleaning
    mask_threshold (float): the mask threshold to calculate the clean cutoff from
    returns (float): the clean cutoff
    """
    clean_cutoff = mask_threshold / c1
    return clean_cutoff


def create_mask(self, image, mask, threshold, theoretical_noise, beampars=None):
    """
    Creates a mask from an image using pybdsf
    image (string): Input image to use in MIRIAD format
    mask (string): Output mask image in MIRIAD format
    threshold (float): Threshold in Jy to use
    theoretical_noise (float): Theoretical noise for calculating the adaptive threshold parameter inside pybdsf
    """
    convim.mirtofits(image, image + '.fits')
    bdsf_threshold = threshold / theoretical_noise
    if beampars is not None:
        bdsf.process_image(image + '.fits', advanced_opts=True, stop_at='isl', thresh_isl = bdsf_threshold, beam=beampars, adaptive_rms_box=True).export_image(outfile=mask + '.fits', img_format='fits', img_type='island_mask', pad_image=True)
    else:
        bdsf.process_image(image + '.fits', advanced_opts=True, stop_at='isl', thresh_isl=bdsf_threshold, adaptive_rms_box=True).export_image(outfile=mask + '.fits', img_format='fits', img_type='island_mask', pad_image=True)
    convim.fitstomir(mask + '.fits', mask + '_pybdsf')
    maths = lib.miriad('maths')
    maths.out = mask
    maths.exp = '"<' + mask + '_pybdsf>"'
    maths.mask = '"<' + mask + '_pybdsf>.gt.0' + '"'
    maths.go()
    managefiles.director(self, 'rm', image + '.fits.pybdsf.log')
    managefiles.director(self, 'rm', image + '.fits')
    managefiles.director(self, 'rm', mask + '.fits')
    managefiles.director(self, 'rm', mask + '_pybdsf')


def get_beam(self, image, beam):
    """
    Get the synthesised beam of an image with has not been cleaned
    image (string): Input image to use in MIRIAD format
    beam (string): Beam image for cleaning in MIRIAD format
    return (tuple): Synthesised beam parameters in the order bmaj, bmin, bpa
    """
    clean = lib.miriad('clean')
    clean.map = image
    clean.beam = beam
    clean.out = 'tmp_beampars.cl'
    clean.niters = 1
    clean.region = 'quarter'
    clean.go()
    restor = lib.miriad('restor')  # Create the restored image
    restor.model = 'tmp_beampars.cl'
    restor.beam = beam
    restor.map = image
    restor.out = 'tmp_beampars.rstr'
    restor.mode = 'clean'
    restor.go()
    convim.mirtofits('tmp_beampars.rstr', 'tmp_beampars.fits')
    pyfile = pyfits.open('tmp_beampars.fits')
    header = pyfile[0].header
    bmaj = header['BMAJ']
    bmin = header['BMIN']
    bpa = header['BPA']
    beampars = bmaj, bmin, bpa
    managefiles.director(self, 'rm', 'tmp_beampars.cl')
    managefiles.director(self, 'rm', 'tmp_beampars.rstr')
    managefiles.director(self, 'rm', 'tmp_beampars.fits')
    return beampars
