"""
Functions to check if a strong source outside of the orimary beam needs to be peeled
"""

import logging
import numpy as np
from apercal.subs import lsm


def check_lsm(infile, cutoff, r1, r2):
    """
    checkpeeling: module to check if a source has an apparant flux density in the NVSS-catalogue higher than the
                  cutoff between r1 and r2 from the pointing centre.
    infile: The input file to calibrate on. Needed for coordinate extraction and freqeuncy information
    cutoff: apparent flux density to consider a source as to be peeled
    r1: radius of primary beam (sources to ignore)
    r2: query radius for NVSS. Only sources between r1 and r2 from the pointing centre will be considered for peeling
    """
    cat = lsm.query_catalogue(infile, 'NVSS', r2, minflux=cutoff)
    if len(cat) > 0:
        cat = lsm.calc_appflux(infile, cat, 'WSRT')
        limidx = np.delete(np.where(cat.dist) < r1), 0  # Find the index of the sources inside the primary beam (r1)
        cat = np.delete(cat, limidx)  # remove the sources inside the primary beam from the list
        if len(cat) > 0:
            logging.info(str(len(cat)) + 'source(s) for peeling found outside the primary beam area!')
    else:
        logging.info(
            'There does not seem to be a atrong source outside of the primary beam! Peeling not needed at this stage!')
        cat = None

# def check_catalogue(infile, cat, peeldir):
#     n_patches = len(cat)
#     for n,p in enumerate(cat):
#
#     return patches

# def write_peeling(outfile, patches):
