"""
This file uses astropy and miriad to construct a catalogue of apparent and real flux densities for a
pointing centre in a certain radius
"""
import logging
import re

import matplotlib.mlab as mplab
import numpy as np
from astropy import units as u
from astropy.coordinates import Angle, SkyCoord
from astroquery.vizier import Vizier

from apercal.libs import lib
from apercal.subs.pb import wsrtBeam
from apercal.subs.readmirhead import getradec


def query_catalogue(infile, catalogue, radius, minflux=0.0):
    """
    query_catalogue: module to query the FIRST, NVSS, or WENSS catalogue from Vizier and write it to a record array

    skycoords: coordinates of the pointing centre in astropy format
    catalogue: catalogue to ask for (NVSS, WENSS, or FIRST)
    radius: radius around the pointing centre to ask for in degreees
    minflux: minimum real source flux to receive from a VIZIER query. Default is 0.0 since for most operations you
             want all sources in the radius region

    returns: record array with RA, DEC, Major axis, Minor axis, parallactic angle, and flux of the sources in the
             catalogue
    """
    try:
        if catalogue == 'FIRST':
            v = Vizier(columns=["*", "+_r", "_RAJ2000", "_DEJ2000", "PA"], column_filters={"Fint": ">" + str(minflux)})
            v.ROW_LIMIT = -1
            sources = v.query_region(getradec(infile), radius=Angle(radius, "deg"), catalog=catalogue)
            maj_axis = sources[0]['Maj']
            min_axis = sources[0]['Min']
            flux = sources[0]['Fint'] / 1000.0
        elif catalogue == 'NVSS':
            v = Vizier(columns=["*", "+_r", "_RAJ2000", "_DEJ2000", "PA"], column_filters={"S1.4": ">" + str(minflux)})
            v.ROW_LIMIT = -1
            sources = v.query_region(getradec(infile), radius=Angle(radius, "deg"), catalog=catalogue)
            maj_axis = sources[0]['MajAxis']
            min_axis = sources[0]['MinAxis']
            flux = sources[0]['S1.4'] / 1000.0
        elif catalogue == 'WENSS':
            v = Vizier(columns=["*", "+_r", "_RAJ2000", "_DEJ2000", "PA"], column_filters={"Sint": ">" + str(minflux)})
            v.ROW_LIMIT = -1
            sources = v.query_region(getradec(infile), radius=Angle(radius, "deg"), catalog=catalogue)
            maj_axis = sources[0]['MajAxis']
            min_axis = sources[0]['MinAxis']
            flux = sources[0]['Sint'] / 1000.0
        catlength = len(sources[0])
        dtype = [('RA', float), ('DEC', float), ('MajAxis', float), ('MinAxis', float), ('PA', float), ('flux', float),
                 ('dist', float)]  # create a structured array with the source data
        cat = np.zeros((catlength,), dtype=dtype)
        cat['RA'] = sources[0]['_RAJ2000']
        cat['DEC'] = sources[0]['_DEJ2000']
        cat['MajAxis'] = maj_axis
        cat['MinAxis'] = min_axis
        cat['PA'] = sources[0]['PA']
        cat['flux'] = flux
        cat['dist'] = sources[0]['_r']
        cat = np.rec.array(cat)  # transform the structured array to a record array for easier handling
    except IndexError:
        cat = []
    return cat


def calc_offset(infile, cat):
    """
    calc_offset: Calculate the offset of the catalogue entries towards the pointing centre
    infile: Input MIRIAD uv-file
    cat: Input catalogue of sources to calculate the offset for
    returns: A catalogue with the offsets for the individual sources
    """
    ra_off = (cat.RA - getradec(infile).ra.deg) * 3600.0 * np.cos(getradec(infile).dec.rad)
    dec_off = (cat.DEC - getradec(infile).dec.deg) * 3600.0
    cat = mplab.rec_append_fields(cat, ['RA_off', 'DEC_off'], [ra_off, dec_off], dtypes=[float, float])
    return cat


def calc_appflux(infile, cat, beam):
    """
    calc_appflux: module to calculate the apparent fluxes of sources from an input catalogue using primary beam correction
    infile: Input MIRIAD uv-file
    cat: catalogue (most likely from query_catalogue)
    beam: the beam type to correct for. Only 'WSRT' allowed at the moment
    returns: an extended catalogue file including the distances RA- and DEC-offsets and apparent fluxes from th
             pointing centre
    """
    if beam == 'WSRT':  # Check which beam model to use. APERTIF going to be included later.
        logging.warning(' Using standard WSRT beam for calculating apparent fluxes!')
    else:
        logging.warning(' Beam model not supported yet! Using standard WSRT beam instead!')
    sep = cat.dist
    appflux = np.zeros((len(cat)))
    for c in range(0, len(cat)):  # calculate the apparent flux of the sources
        appflux[c] = (cat.flux[c]) * wsrtBeam(sep[c], getfreq(infile))
    cat = mplab.rec_append_fields(cat, ['appflux'], [appflux], dtypes=[float])
    return cat


def sort_catalogue(catalogue, column):
    """
    Sorts a catalogue after a certain column. Most likely after a calc_appflux call to generate a
    flux sorted local skymodel

    catalogue: an input catalogue (most likely from a query_catalogue call)
    column: the column to sort for
    returns: an updated sorted catalogue
    """
    cat = np.sort(catalogue, order=column)[::-1]  # Sort the array in descending order
    return cat


def cutoff_catalogue(catalogue, cutoff):
    """
    cutoff_catalogue: limit the entries of a catalogue to the strongest sources in the field giving a cutoff
    catalogue: catalogue to limit (most likely after primary beam correction and sorting)
    cutoff: cutoff is defined as the part of the flux of all sources in the catalogue (0.0-1.0)
    returns: a catalogue with the weak sources removed according to the cutoff parameter
    """
    allflux = np.sum(catalogue.appflux)
    logging.debug(' Field seems to have a flux of ' + str(allflux) + ' Jy')
    limflux = allflux * cutoff  # determine the cutoff
    cat = sort_catalogue(catalogue, 'appflux')
    limidx = np.delete(np.where(np.cumsum(cat.appflux) > limflux),
                       0)  # find the index of the sources above the cutoff to remove them from the list
    cat = np.delete(cat, limidx)  # remove the faint sources from the list
    usedflux = np.sum(cat.appflux)
    logging.debug(' Found ' + str(len(cat)) + ' source(s) in the model at a cutoff of ' + str(
        cutoff * 100) + ' percent with a total flux of ' + str(usedflux) + ' Jy')
    return cat


def calc_SI(cat1, cat2, limit):
    """
    module to use a catalogue at a different frequency, do cross matching, and calculate the spectral index
    The module also looks for multiple matches and assigns the flux of one source matching multiple ones linearly to
    calculate the spectral index. I tonly looks into sources which are not further apart as the limit parameter.

    cat1: The catalogue where you want to add the spectral index to the sources. Usually NVSS or FIRST.
    cat2: The catalogue to match and calculate the spectral index from. Usually WENSS.
    limit: Maximum distance in arcseconds for two sources to match each other.
    returns: cat1 with added spectral indices. Sources with no counterpart where set to -0.7.
    """
    try:  # Handle the exception if the WENSS query did not give any results.
        coords1 = SkyCoord(ra=cat1.RA, dec=cat1.DEC, unit=(
            u.deg, u.deg))  # Convert the coordinates of the two source catalogues to the right format
        coords2 = SkyCoord(ra=cat2.RA, dec=cat2.DEC, unit=(u.deg, u.deg))
        idx, d2d, d3d = coords1.match_to_catalog_sky(
            coords2)  # Get the indices of the matches (idx), and their distance on the sky (d2d)
        dist = (d2d * u.deg * 3600) / (u.deg * u.deg)  # Convert to arcsec
        nomatch = np.where(dist > limit)  # Index of sources with no match
        match = np.where(dist <= limit)  # Index of sources with match
        idx_match = idx[match]
        flux1 = np.delete(cat1.flux,
                          nomatch)  # Array of source fluxes at 20cm for all matches including resolved sources
        flux2 = np.asarray(cat2.flux)[idx_match]  # Array of source fluxes at 90cm for all matches including multiples
        src, counts = np.unique(idx_match, return_counts=True)
        logging.debug(' Found ' + str(len(np.asarray(nomatch)[0])) + ' source(s) with no counterparts. Setting their spectral index to -0.7')
        num, occ = np.unique(counts, return_counts=True)
        for n, g in enumerate(num):
            logging.debug(' Found ' + str(occ[n]) + ' source(s) with ' + str(num[n]) + ' counterpart(s)')
        src_wgt_1 = np.zeros(len(flux2))  # Calculate the fluxes for the matched and resolved sources using weighting
        for s in src:
            src_idx = np.where(s == idx_match)
            src_sum_1 = np.sum(flux1[src_idx])
            src_wgt_1[src_idx] = flux1[src_idx] / src_sum_1
        src_flux_2 = flux2 * src_wgt_1
        src_si = np.log10(flux1 / src_flux_2) / np.log10(1.4 / 0.33)
        si = np.zeros(len(idx))  # Create the array for the spectral index and put the values into the right position
        si[nomatch] = -0.7
        si[match] = src_si
        si[si < -3] = -0.7
        # Change the value to -0.7 in case of high absolute values. Maybe wrong source match or variable source
        si[si > 2] = -0.7
        cat = mplab.rec_append_fields(cat1, 'SI', si, dtypes=float)
    except Exception:
        # In case the queried area is not covered by WENSS give all sources a spectral index of -0.7.
        cat = mplab.rec_append_fields(cat1, 'SI', -0.7, dtypes=float)
    return cat


def lsm_model(infile, radius, cutoff, limit):
    """
    lsm_model: Create a file to use for the MIRIAD task uvmodel to create a dataset for doing parametric self-calibration
    infile: The MIRIAD (u,v)-dataset to calibrate on to get frequency and pointing information
    radius: The radius for the cone search to consider sources for the skymodel
    cutoff: The percentage of total apparent flux of the field to use for the skymodel (0.0-1.0)
    limit: The distance in arcseconds for considering a source as a match for the source matching algorithm to
          calculate the spectral indices
    returns: A catalogue of sources with spectral indices and the set cutoff. Used as input for write_model.
    """
    cat = query_catalogue(infile, 'FIRST', radius)
    if len(cat) == 0:  # Handle the exception if the field to calibrate is not in FIRST. Use NVSS instead.
        cat = query_catalogue(infile, 'NVSS', radius)
    try:  # Handle the exception if the covered field is not in WENSS
        low_cat = query_catalogue(infile, 'WENSS', radius)
    except Exception:
        low_cat = None
    cat = calc_SI(cat, low_cat, limit)
    cat = calc_offset(infile, cat)
    cat = calc_appflux(infile, cat, 'WSRT')
    cat = sort_catalogue(cat, 'appflux')
    cat = cutoff_catalogue(cat, cutoff)
    return cat


def lsm_mask(infile, radius, cutoff, catalogue):
    """
    lsm_mask: Create a file for the MIRIAD task imgen to create a mask for the first iteration of the self-calibration
    infile: The MIRIAD (u,v)-dataset to calibrate on to get frequency and pointing information
    radius: The radius for the cone search to consider sources for the mask
    cutoff: The percentage of total apparent flux of the field to use for the mask (0.0-1.0)
    catalogue: The source catalogue to query (usually NVSS or FIRST)
    returns: A catalogue with the sources for the mask. Usually used for write_mask
    """
    cat = query_catalogue(infile, catalogue, radius)
    cat = calc_offset(infile, cat)
    cat = calc_appflux(infile, cat, 'WSRT')
    cat = sort_catalogue(cat, 'appflux')
    cat = cutoff_catalogue(cat, cutoff)
    return cat


def write_model(outfile, cat):
    """
    write_model: Module to write a file used for the MIRIAD task uvmodel to do a parametric self-calibration
    outfile: The output file to write to
    cat: The catalogue to use for the file to write
    """
    srctext = ''
    appflux = cat.appflux
    ra_off = cat.RA_off
    dec_off = cat.DEC_off
    si = cat.SI
    for i, x in enumerate(appflux):
        srctext = srctext + str(ra_off[i]) + ',' + str(dec_off[i]) + ',' + str(appflux[i]) + ',1.4,' + str(si[i]) + '\n'
    mirmdlfile = open(outfile, 'w')
    mirmdlfile.write(srctext)
    mirmdlfile.close()
    logging.debug(' Wrote source textfile to ' + str(outfile) + '!')


def write_mask(outfile, cat):
    """
    write_mask: Module to write a file used for the MIRIAD task imgen to create a first mask for self-calibration
    outfile: The output file to write to
    cat: The catalogue to use for the file to write
    """
    msktext1 = ''
    msktext2 = ''
    ra_off = cat.RA_off
    dec_off = cat.DEC_off
    majaxis = cat.MajAxis
    minaxis = cat.MinAxis
    pa = np.nan_to_num(cat.PA)
    for i, x in enumerate(ra_off):
        msktext1 = msktext1 + 'gaussian,'
        msktext2 = msktext2 + '1,' + str(int(ra_off[i])) + ',' + str(int(dec_off[i])) + ',' + str(
            int(majaxis[i])) + ',' + str(int(minaxis[i])) + ',' + str(int(pa[i])) + ','
    msktext = msktext1[:-1] + '\n' + msktext2[:-1]
    mirmskfile = open(outfile, 'w')
    mirmskfile.write(msktext)
    mirmskfile.close()
    logging.debug(' Wrote mask textfile to ' + str(outfile) + '!')


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
