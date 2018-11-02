import re

import numpy as np
from astropy import units as u
from astropy.coordinates import FK5, SkyCoord

from apercal.libs import lib


def getraimage(infile):
    """
    getraimage: Get the RA cooridinate from a miriad image
    infile (string): input image file in MIRIAD format
    returns: RA coordinates of the image in hh:mm:ss.sss
    """
    prthd = lib.basher('prthd in=' + infile)
    regex = re.compile(".*(RA---NCP).*")
    coordline = [m.group(0) for l in prthd for m in [regex.search(l)] if m][0].split()
    ra = coordline[2]
    return ra


def getdecimage(infile):
    """
    getdecimage: Get the DEC from a MIRIAD image
    infile (string): input image file in MIRIAD format
    returns: DEC coordinates dd:mm:ss.sss
    """
    prthd = lib.basher('prthd in=' + infile)
    regex = re.compile(".*(DEC--NCP).*")
    coordline = [m.group(0) for l in prthd for m in [regex.search(l)] if m][0].split()
    dec = coordline[2]
    return dec


def getbmajimage(infile):
    """
    getbmajimage: Get the major beam size from a MIRIAD image
    infile (string): input image file in MIRIAD format
    returns (float): BMAJ in arcseconds of the image
    """
    bmaj = np.float(lib.basher('gethd in=' + infile + '/bmaj')[0]) * 3600.0 * (360.0 / (2.0 * np.pi))
    return bmaj


def getbminimage(infile):
    """
    getbminimage: Get the minor beam size from a MIRIAD image
    infile (string): input image file in MIRIAD format
    returns (float): BMIN in arcseconds of the image
    """
    bmin = np.float(lib.basher('gethd in=' + infile + '/bmin')[0]) * 3600.0 * (360.0 / (2.0 * np.pi))
    return bmin


def getbpaimage(infile):
    """
    getbmpaimage: Get the beam angle from a MIRIAD image
    infile (string): input image file in MIRIAD format
    returns (float): BPA in degrees of the image
    """
    bpa = np.float(lib.basher('gethd in=' + infile + '/bpa')[0])
    return bpa


def getbeamimage(infile):
    """
    Uses the three functions above to return the beam parameters of an image (bmaj, bmin, bpa)
    infile (string): input image file in MIRIAD format
    returns (numpyarray): The bmaj, bmin, bpa of the image
    """
    beamarray = np.full(3, np.nan)
    beamarray[0] = getbmajimage(infile)
    beamarray[1] = getbminimage(infile)
    beamarray[2] = getbpaimage(infile)
    return beamarray


def getradec(infile):
    """
    getradec: module to extract the pointing centre ra and dec from a miriad image file. Uses the PRTHD task in miriad
    inputs: infile (name of file)
    returns: coords, an instance of the astropy.coordinates SkyCoord class which has a few convenient attributes.
    """
    prthd = lib.basher('prthd in=' + infile)
    regex = re.compile(".*(J2000).*")
    coordline = [m.group(0) for l in prthd for m in [regex.search(l)] if m][0].split()
    rastr = coordline[3]
    decstr = coordline[5]
    rastr = fixra(rastr)
    coords = SkyCoord(FK5, ra=rastr, dec=decstr, unit=(u.deg, u.deg))
    return coords


def fixra(ra0):
    """
    fixra: module to fix the notation of the ra string
    ra0: input ra notation from a skycoords query
    returns: the fixed notation for the ra
    """
    R = ''
    s = 0
    for i in ra0:
        if i == ':':
            if s == 0:
                R += 'h'
                s += 1
            else:
                R += 'm'
        else:
            R += i
    return R


def getradecsex(infile):
    """
    skycoords: The astropy SkyCoord instance values to covert to a string
    returns: String with the RA and DEC in format hh:mm:ss,dd:mm:ss
    """
    prthd = lib.basher('prthd in=' + infile)
    regex = re.compile(".*(J2000).*")
    coordline = [m.group(0) for l in prthd for m in [regex.search(l)] if m][0].split()
    coords = coordline[3].split('.')[0] + ',' + coordline[5].split('.')[0]
    return coords


def getfreq(infile):
    """
    getfreq: module to extract the central freqeuncy of the observing band
    param infile: infile (name of file)
    returns: the central frequency of the visibility file
    """
    prthd = lib.basher('prthd in=' + infile)
    regex = re.compile(".*(GHz).*")
    freqline = [m.group(0) for l in prthd for m in [regex.search(l)] if m][0].split()
    freq = float(freqline[2]) + (float(freqline[1]) / 2.0) * float(freqline[3])
    return freq


def getnchan(infile):
    """
    getnchan: module to extract the number of channels from an observation
    param infile: infile (name of file)
    return: the number of channels of the observation
    """
    prthd = lib.basher('prthd in=' + infile)
    regex = re.compile(".*(GHz).*")
    nchanline = [m.group(0) for l in prthd for m in [regex.search(l)] if m][0].split()
    nchan = int(nchanline[1])
    return nchan
