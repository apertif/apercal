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
    Subroutine to calculate the min, max and rms of an image
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


def getmaskstats(self, image, size):
    """
    Subroutine to calculate the number of pixels in a mask and its percentage of the full image
    image (string): The absolute path to the image file.
    size (int): Number of pixels along an axis of the original image. Assumes square images.
    returns (numpy array): The number of pixels and their percentage of the full image
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
            mask_data = pyfits.open(tempdir + '/' + temp_string + '.fits')
        elif os.path.isfile(image):
            mask_data = pyfits.open(image)
        else:
            error = 'Image format not supported. Only MIRIAD and FITS formats are supported!'
            logger.error(error)
            raise ApercalException(error)

        data = mask_data[0].data
        maskstats = np.full(2, np.nan)
        maskstats[0] = np.count_nonzero(~np.isnan(data))
        maskstats[1] = maskstats[0]/(size**2)
        mask_data.close()
        managetmp.clean_tempdir('images')
    else:
        error = 'Image does not seem to exist!'
        logger.error(error)
        raise ApercalException(error)

    return maskstats


def getmodelstats(self, image):
    """
    Subroutine to calculate the number of clean components and their flux
    image (string): The absolute path to the image file.
    returns (numpy array): The number of pixels with clean components and their summed flux in Jy
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
            model_data = pyfits.open(tempdir + '/' + temp_string + '.fits')
        elif os.path.isfile(image):
            model_data = pyfits.open(image)
        else:
            error = 'Image format not supported. Only MIRIAD and FITS formats are supported!'
            logger.error(error)
            raise ApercalException(error)

        data = model_data[0].data[:,0,:,:]
        modelstats = np.full(2, np.nan)
        modelstats[0] = np.count_nonzero(data)
        modelstats[1] = np.sum(data)
        model_data.close()
        managetmp.clean_tempdir('images')
    else:
        error = 'Image does not seem to exist!'
        logger.error(error)
        raise ApercalException(error)

    return modelstats


def getcubestats(self, cube):
    """
    Subroutine to calculate the max,min and rms of a cube along the frequency axis
    cube (string): The absolute path to the image cube file.
    returns (numpy array): The min, max and rms of the image
    """
    setinit.setinitdirs(self)
    char_set = string.ascii_uppercase + string.digits
    if os.path.isdir(cube) or os.path.isfile(cube):
        if os.path.isdir(cube):
            tempdir = managetmp.manage_tempdir('images')
            temp_string = ''.join(random.sample(char_set * 8, 8))
            fits = lib.miriad('fits')
            fits.op = 'xyout'
            fits.in_ = cube
            fits.out = tempdir + '/' + temp_string + '.fits'
            fits.go()
            cube_data = pyfits.open(tempdir + '/' + temp_string + '.fits')
        elif os.path.isfile(cube):
            cube_data = pyfits.open(cube)
        else:
            error = 'Image format not supported. Only MIRIAD and FITS formats are supported!'
            logger.error(error)
            raise ApercalException(error)

        data = cube_data[0].data
        cubestats = np.full((3,data.shape[1]), np.nan)
        cubestats[0] = np.nanmin(data, axis=(0, 2, 3))  # Get the maxmimum of the image
        cubestats[1] = np.nanmax(data, axis=(0, 2, 3))  # Get the minimum of the image
        cubestats[2] = np.nanstd(data, axis=(0, 2, 3))  # Get the standard deviation
        cube_data.close()  # Close the image
        managetmp.clean_tempdir('images')
    else:
        error = 'Image does not seem to exist!'
        logger.error(error)
        raise ApercalException(error)

    return cubestats