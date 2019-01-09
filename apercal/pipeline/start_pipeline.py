#!/usr/bin/env python

from __future__ import print_function

import matplotlib as mpl
from apercal.modules.prepare import prepare
from apercal.modules.preflag import preflag
from apercal.modules.ccal import ccal
from apercal.modules.convert import convert
from apercal.subs import calmodels as subs_calmodels
import socket
import apercal
import os
import subprocess
import apercal.libs.lib as lib
from apercal.subs.msutils import get_source_name
import logging
import sys
from time import time
from datetime import timedelta

mpl.use('TkAgg')


def validate_taskid(taskid_from_autocal):
    """Parses a taskid from autocal, returns empty string or the proper taskid

    Args:
        taskid_from_autocal (str): task id from autocal, e.g. 20180403-003 or None
    Returns:
        str: Task id that is accepted by prepare step, e.g. '003' or ''
    """
    if taskid_from_autocal and len(str(taskid_from_autocal)) > 3:
        return str(taskid_from_autocal)[-3:]
    else:
        return ''


def start_apercal_pipeline(targets, fluxcals, polcals, dry_run=False):
    """
    Trigger the start of a fluxcal pipeline. Returns when pipeline is done.
    Example for taskid, name, beamnr: (190108926, '3C147_36', 36)
    Fluxcals and polcals can be specified in the wrong order, if the polcal is not polarised
    they will be flipped.
    Only one polcal beam is supported for now.

    Args:
        targets (Tuple[int, str, List[int]]): taskid, name, list of beamnrs
        fluxcals (List[Tuple[int, str, int]]): fluxcals: taskid, name, beamnr
        polcals (List[Tuple[int, str, int]]): polcals: taskid, name, beamnr (can be None)
        dry_run (bool): interpret arguments, do not actually run pipeline

    Returns:
        Tuple[bool, str]: True if the pipeline succeeds, informative message
    """
    (taskid_target, name_target, beamlist_target) = targets

    basedir = '/data/apertif/{}/'.format(taskid_target)
    if not os.path.exists(basedir):
        os.mkdir(basedir)

    logfilepath = os.path.join(basedir, 'apercal.log')

    lib.setup_logger('debug', logfile=logfilepath)
    logger = logging.getLogger(__name__)
    gitinfo = subprocess.check_output('cd ' + os.path.dirname(apercal.__file__) +
                                      '&& git describe --tag; cd', shell=True).strip()
    logger.info("Apercal version: " + gitinfo)

    name_fluxcal = str(fluxcals[0][1]).strip().split('_')[0]
    if polcals:
        name_polcal = str(polcals[0][1]).strip().split('_')[0]
    else:
        name_polcal = ''
    name_target = str(name_target).strip()

    # Exchange polcal and fluxcal if specified in the wrong order
    if not subs_calmodels.is_polarised(name_polcal):
        if subs_calmodels.is_polarised(name_fluxcal):
            logger.debug("Switching polcal and fluxcal because " + name_polcal +
                         " is not polarised")
            fluxcals, polcals = polcals, fluxcals
            name_polcal = str(polcals[0][1]).strip().split('_')[0]
        else:
            logger.debug("Setting polcal to '' since " + name_polcal + " is not polarised")
            name_polcal = ""
    else:
        logger.debug("Polcal " + name_polcal + " is polarised, all good")

    if name_polcal != "":
        taskid_polcal, name_polcal, beamnr_polcal = polcals[0]

    def name_to_ms(name):
        if not name:
            return ''
        else:
            return name + '.MS'

    def set_files(p):
        """
        Set the basedir, fluxcal, polcal, target properties

        Args:
            p (BaseModule): apercal step object (e.g. prepare)

        Returns:
            None
        """
        p.basedir = basedir
        p.fluxcal = name_to_ms(name_fluxcal)
        p.polcal = name_to_ms(name_polcal)
        p.target = name_to_ms(name_target)

    time_start = time()
    try:
        # Prepare
        p0 = prepare()
        p0.basedir = basedir
        # Prepare target and polcal
        p0.fluxcal = ''
        p0.polcal = name_to_ms(name_polcal)
        p0.target = name_to_ms(name_target)
        p0.prepare_target_beams = ','.join(['{:02d}'.format(beamnr) for beamnr in beamlist_target])
        p0.prepare_obsnum_target = validate_taskid(taskid_target)
        if not dry_run:
            p0.go()

        # Prepare fluxcals
        for (taskid_fluxcal, name_fluxcal, beamnr_fluxcal) in fluxcals:
            p0.prepare_target_beams = str(beamnr_fluxcal)
            p0.prepare_date = str(taskid_fluxcal)[:6]
            p0.prepare_obsnum_target = validate_taskid(taskid_fluxcal)
            if not dry_run:
                p0.go()

        p1 = preflag()
        set_files(p1)

        if not dry_run:
            p1.go()

        p2 = ccal()
        set_files(p2)

        if not dry_run:
            p2.go()

        p3 = convert()
        set_files(p3)
        if not dry_run:
            p3.go()

        time_end = time()
        msg = "Apercal finished after " + str(timedelta(seconds=time() - time_start))
        logger.info(msg)
        return True, msg
    except Exception as e:
        time_end = time()
        msg = "Apercal threw an error after " + str(timedelta(seconds=time() - time_start))
        logger.exception(msg)
        return False, msg + '\n' + str(e) + '\n' + "Check log at " + socket.gethostname() + ':' + logfilepath
