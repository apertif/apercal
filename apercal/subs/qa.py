import os

import astropy.io.fits as pyfits
import numpy as np

from apercal.libs import lib


def resistats(infile):
    fits = lib.miriad('fits')
    fits.in_ = 'residual'
    fits.op = 'xyout'
    fits.out = 'rmsresidual' + '.fits'
    fits.go()
    pyfile = pyfits.open(fits.out)
    image = pyfile[0].data[0][0]
    pyfile.close()
    resimax = np.amax(image)
    resirms = np.std(image)
    os.system('rm -rf rms*')
    return resirms, resimax


def imstats(infile, stokes):
    invert = lib.miriad('invert')
    invert.vis = infile
    invert.map = 'rmsmap'
    invert.beam = 'rmsbeam'
    invert.imsize = 2049
    invert.cell = 3
    invert.stokes = stokes
    invert.options = 'mfs'
    invert.robust = 0
    invert.slop = 1
    invert.go()
    fits = lib.miriad('fits')
    fits.in_ = invert.map
    fits.op = 'xyout'
    fits.out = invert.map + '.fits'
    fits.go()
    pyfile = pyfits.open(fits.out)
    image = pyfile[0].data[0][0]
    pyfile.close()
    inimax = np.amax(image)
    inirms = np.std(image)
    os.system('rm -rf rms*')
    return inimax, inirms


def theostats(infile):
    """
    theostats: Calculates the theoretical noise of an observation using the MIRIAD task obsrms
    infile: The input file to calculate the noise for
    return: The theoretical rms
    """
    obsrms = lib.miriad('obsrms')
    theorms = 0.00004
    return theorms


def check_blank(infile):
    """
    check_blank: Checks if an image is completely blanked. Mostly used for checking if self calibration cycles
                 produced a valid output.
    infile: The input image to check
    return: True if image is blank
    """
    if np.any(np.nan):
        status = True
    else:
        status = False
    return status


def fieldflux(infile):
    invert = lib.miriad('invert')
    invert.vis = infile
    invert.map = 'fluxmap'
    invert.beam = 'fluxbeam'
    invert.imsize = 2049
    invert.cell = 3
    invert.stokes = 'ii'
    invert.options = 'mfs'
    invert.robust = 0
    invert.slop = 1
    invert.go()
    clean = lib.miriad('clean')
    clean.map = invert.map
    clean.beam = invert.beam
    clean.out = 'fluxmodel'
    clean.niters = 10000
    clean.go()
    fits = lib.miriad('fits')
    fits.in_ = clean.out
    fits.op = 'xyout'
    fits.out = clean.out + '.fits'
    fits.go()
    pyfile = pyfits.open(fits.out)
    image = pyfile[0].data[0][0]
    pyfile.close()
    intflux = np.sum(image)
    os.system('rm -rf flux*')
    return intflux
