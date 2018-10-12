#!/usr/bin/env python

# ALTA data transfer: Uses the iROD client to transfer data from ALTA
# Example usage: >> python getdata_alta.py 180316 004-010 00-36
# V.A. Moss (vmoss.astro@gmail.com)
from __future__ import print_function

__author__ = "V.A. Moss"
__date__ = "$20-mar-2018 16:00:00$"
__version__ = "0.2"

import os
import sys
import time
import argparse
import logging


def parse_list(spec):
    """Convert a string specification like 00-04,07,09-12 into a list [0,1,2,3,4,7,9,10,11,12]

    Args:
        spec (str): string specification

    Returns:
        List[int]

    Example:
        >>> parse_list("00-04,07,09-12")
        [0, 1, 2, 3, 4, 7, 9, 10, 11, 12]
        >>> parse_list("05-04")
        Traceback (most recent call last):
            ...
        ValueError: In specification 05-04, end should not be smaller than begin
    """
    ret_list = []
    for spec_part in spec.split(","):
        if "-" in spec_part:
            begin, end = spec_part.split("-")
            if end<begin:
                raise ValueError("In specification %s, end should not be smaller than begin"%spec_part)
            ret_list += range(int(begin), int(end)+1)
        else:
            ret_list += [int(spec_part)]

    return ret_list

def get_alta_dir(date, task_id, beam_nr, alta_exception):
    """Get the directory where stuff is stored in ALTA. Takes care of different historical locations

    Args:
        date (str): date for which location is requested
        task_id (int): task id
        beam_nr (int): beam id
        alta_exception (bool): force 3 digits task id, old directory

    Returns:
        str: location in ALTA, including the date itself

    Examples:
        >>> get_alta_dir(180201, 5, 35, False)
        '/altaZone/home/apertif_main/wcudata/WSRTA18020105/WSRTA18020105_B035.MS'
        >>> get_alta_dir(180321, 5, 35, False)
        '/altaZone/home/apertif_main/wcudata/WSRTA180321005/WSRTA180321005_B035.MS'
        >>> get_alta_dir(181205, 5, 35, False)
        '/altaZone/archive/apertif_main/visibilities_default/181205005/WSRTA181205005_B035.MS'
    """
    if int(date) < 180216:
        return "/altaZone/home/apertif_main/wcudata/WSRTA{date}{task_id:02d}/WSRTA{date}{task_id:02d}_B{beam_nr:03d}.MS".format(**locals())
    elif int(date) < 181003 or alta_exception:
        return "/altaZone/home/apertif_main/wcudata/WSRTA{date}{task_id:03d}/WSRTA{date}{task_id:03d}_B{beam_nr:03d}.MS".format(**locals())
    else:
        return "/altaZone/archive/apertif_main/visibilities_default/{date}{task_id:03d}/WSRTA{date}{task_id:03d}_B{beam_nr:03d}.MS".format(**locals())
 
def getdata_alta(date, task_ids, beams, targetdir=".", tmpdir=".", alta_exception=False):
    """Download data from ALTA using low-level IRODS commands.
    Report status to slack

    Args:
        data (str): date of the observation
        task_ids (List[int] or int): list of task_ids, or a single task_id (int)
        beams (List[int] or int): list of beam numbers, or a single beam number (int)
        targetdir (str): directory to put the downloaded files
        tmpdir (str): directory for temporary files
        alta_exception (bool): force 3 digits task id, old directory
    """
    # Time the transfer
    start = time.time()
    logger = logging.getLogger("GET_ALTA")
    logger.setLevel(logging.DEBUG)

    if isinstance(task_ids, int):
        task_ids = [task_ids]
    if isinstance(beams, int):
        beams = [beams]

    if tmpdir == "":
        tmpdir = "."
    if targetdir == "":
        targetdir = "."

    if tmpdir[-1] != "/":
        tmpdir += "/"
    if targetdir[-1] != "/":
        targetdir += "/"

    logger.info('########## Start getting data from ALTA ##########')
    logging.info('Beams: %s'%beams)

    for beam_nr in beams:

        logger.info('###### Processing beam %.3d... ######' % beam_nr)

        for task_id in task_ids:
            logger.info('Processing task ID %.3d...' % task_id)

            alta_dir = get_alta_dir(date, task_id, beam_nr, alta_exception)
            cmd = "iget -rfPIT -X {tmpdir}WSRTA{date}{task_id:03d}_B{beam_nr:03d}-icat.irods-status --lfrestart {tmpdir}WSRTA{date}{task_id:03d}_B{beam_nr:03d}-icat.lf-irods-status --retries 5 {alta_dir} {targetdir}".format(**locals())
            logger.info(cmd)
            os.system(cmd)

    os.system('rm -rf {tmpdir}*irods-status'.format(**locals()))

    # Add verification at the end of the transfer
    for beam_nr in beams:

        logger.info('###### Verifying beam %.3d... ######' % beam_nr)

        for task_id in task_ids:
            logger.info('Verifying task ID %.3d...' % task_id)

            # Toggle for when we started using more digits:
            alta_dir = get_alta_dir(date, task_id, beam_nr, alta_exception)
            cmd = "irsync -srl i:{alta_dir} {targetdir}WSRTA{date}{task_id:03d}_B{beam_nr:03d}.MS >> {tmpdir}transfer_WSRTA{date}{task_id:03d}_to_alta_verify.log 2>&1".format(**locals())

            os.system(cmd)

    # Identify server details
    hostname = os.popen('hostname').read().strip()
    path = os.popen('pwd').read().strip() # not using this for now but maybe in future

    # Check for failed files
    for task_id in task_ids:
        logger.info('Checking failed files for task ID %.3d...' % task_id)

        cmd = os.popen('cat {tmpdir}transfer_WSRTA{date}{task_id:03d}_to_alta_verify.log | wc -l'.format(**locals()))
        for x in cmd:
            logger.warning('Failed files: %s',x.strip())
            failed_files = x.strip()

        if failed_files == '0':
            cmd = """curl -X POST --data-urlencode 'payload={"text":"Transfer of WSRTA%s%.3d (B%.3d-B%.3d) from ALTA to %s finished."}' https://hooks.slack.com/services/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""" % (date,task_id,beams[0],beams[-1],hostname)
        else:
            cmd = """curl -X POST --data-urlencode 'payload={"text":"Transfer of WSRTA%s%.3d (B%.3d-B%.3d) from ALTA to %s finished incomplete. Check logs!"}' https://hooks.slack.com/services/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""" % (date,task_id,beams[0],beams[-1],hostname)

        # Execute the command
        os.system(cmd)

    # Time the transfer
    end = time.time()

    # Print the results
    diff = (end-start)/60. # in min
    logger.info("Total time to transfer data: %.2f min" % diff)
    logger.info("########## Done getting data from ALTA ##########")


if __name__ == "__main__":
    import doctest
    doctest.testmod()

    logging.basicConfig()

    args = sys.argv
    # Get date
    try:
        date = args[1]
    except:
        print("Date required! Format: YYMMDD e.g. 180309")
        sys.exit()

    # Get date
    try:
        irange = args[2]
    except:
        print("ID range required! Format: NNN-NNN e.g. 002-010")
        sys.exit()

    # Get beams
    try:
        brange = args[3]
    except:
        print("Beam range required! Format: NN-NN e.g. 00-37")
        sys.exit()

    # Get beams
    try:
        alta_exception = args[4]
        if alta_exception == 'Y':
            alta_exception = True
        else:
            alta_exception = False
    except:
        alta_exception = False

    # Now with all the information required, loop through beams
    beams = parse_list(brange)

    # Now with all the information required, loop through task_ids
    task_ids = parse_list(irange)

    getdata_alta(date, task_ids, beams, ".", ".", alta_exception)
