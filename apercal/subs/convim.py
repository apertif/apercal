from apercal.libs import lib


def mirtofits(mirimage, fitsimage):
    """
    Convert a MIRIAD image to a fits image
    mirimage (string): The MIRIAD image to convert
    fitsimage (string): The output FITS image
    """
    fits = lib.miriad('fits')
    fits.op = 'xyout'
    fits.in_ = mirimage
    fits.out = fitsimage
    fits.go()


def fitstomir(fitsimage, mirimage):
    """
    Convert a MIRIAD image to a fits image
    mirimage (string): The MIRIAD image to convert
    fitsimage (string): The output FITS image
    """
    fits = lib.miriad('fits')
    fits.op = 'xyin'
    fits.in_ = fitsimage
    fits.out = mirimage
    fits.go()