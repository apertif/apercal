import astropy.io.fits as pyfits
import numpy as np
import os
import random
import string
import logging

from apercal.libs import lib
from apercal.subs import setinit, managetmp
from apercal.exceptions import ApercalException

logger = logging.getLogger(__name__)


def getimagestats(self, image):
    """
    Subroutine to calculate the max,min and rms of an image
    image (string): The absolute path to the image file.
    returns (numpy array): The min, max and rms of the image
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
            image_data = pyfits.open(tempdir + '/' + temp_string + '.fits')
        elif os.path.isfile(image):
            image_data = pyfits.open(image)
        else:
            error = 'Image format not supported. Only MIRIAD and FITS formats are supported!'
            logger.error(error)
            raise ApercalException(error)

        data = image_data[0].data
        imagestats = np.full(3, np.nan)
        imagestats[0] = np.nanmin(data)  # Get the maxmimum of the image
        imagestats[1] = np.nanmax(data)  # Get the minimum of the image
        imagestats[2] = np.nanstd(data)  # Get the standard deviation
        image_data.close()  # Close the image
        managetmp.clean_tempdir('images')
    else:
        error = 'Image does not seem to exist!'
        logger.error(error)
        raise ApercalException(error)

    return imagestats
