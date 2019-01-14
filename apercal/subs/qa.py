import os
import random
import string
import logging

import astropy.io.fits as pyfits
import numpy as np
import scipy.stats

from apercal.libs import lib
from apercal.subs import setinit, managetmp
from apercal.exceptions import ApercalException
from apercal.subs import imstats

logger = logging.getLogger(__name__)


def checkimagegaussianity(self, image, alpha):
    """
    Subroutine to check if an image has gaussian distribution
    image (string): The path/name of the image to check in FITS-format
    returns (boolean): True if image is ok, False otherwise
    """
    setinit.setinitdirs(self)
    char_set = string.ascii_uppercase + string.digits
    if os.path.isdir(image) or os.path.isfile(image):
        if os.path.isdir(image):
            tempdir = managetmp.manage_tempdir('images')
            temp_string = ''.join(random.sample(char_set * 8, 8))
            fits = lib.miriad('fits')
            fits.op = 'xyout'
            fits.in_ = image
            fits.out = tempdir + '/' + temp_string + '.fits'
            fits.go()
            pyfile = pyfits.open(tempdir + '/' + temp_string + '.fits')
        elif os.path.isfile(image):
            pyfile = pyfits.open(image)
        else:
            error = 'Image format not supported. Only MIRIAD and FITS formats are supported!'
            logger.error(error)
            raise ApercalException(error)
        image = pyfile[0].data[0][0]
        pyfile.close()
        k2, p = scipy.stats.normaltest(image, nan_policy='omit', axis=None)
        if p < alpha:
            return True
        else:
            return False
    else:
        error = 'Image does not seem to exist!'
        logger.error(error)
        raise ApercalException(error)


def checkdirtyimage(self, image):
    """
    Subroutine to check if a dirty image is valid
    image (string): The path/name of the image to check
    returns (boolean): True if image is ok, False otherwise
    """
    dirtystats = imstats.getimagestats(self, image)
    if (dirtystats[1] >= dirtystats[0]) and (dirtystats[2] != np.nan):
        return True
    else:
        return False


def checkmaskimage(self, image):
    """
    Checks if a mask is completely blanked.
    image: The input mask to check
    return: True if mask is not blank
    """
    maskstats = imstats.getimagestats(self, image)
    if np.isnan(maskstats[0]) or np.isnan(maskstats[1]) or np.isnan(maskstats[2]):
        return False
    else:
        return True


def checkmodelimage(self, image):
    """
    Subroutine to check if a model image is valid
    image (string): The path/name of the image to check
    returns (boolean): True if image is ok, False otherwise
    """
    modelstats = imstats.getimagestats(self, image)
    if modelstats[2] != np.nan and modelstats[1] <= 1000 and modelstats[0] >= -2.0:
        return True
    else:
        return False


def checkrestoredimage(self, image):
    """
    Subroutine to check if a restored image is valid
    image (string): The path/name of the image to check
    returns (boolean): True if image is ok, False otherwise
    """
    restoredstats = imstats.getimagestats(self, image)
    if restoredstats[2] != np.nan and restoredstats[1] <= 1000 and restoredstats[0] >= -1.0:
        return True
    else:
        return False


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
