#!/usr/bin/env python

from __future__ import print_function

import matplotlib as mpl
from apercal.modules.prepare import prepare
from apercal.modules.preflag import preflag
from apercal.modules.ccal import ccal
from apercal.modules.convert import convert
from apercal.subs import calmodels as subs_calmodels
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


def start_apercal_pipeline((taskid_fluxcal, name_fluxcal, beamlist_fluxcal),
                           (taskid_polcal, name_polcal, beamlist_polcal),
                           (taskid_target, name_target, beamlist_target)):
    """
    Trigger the start of a fluxcal pipeline. Returns immediately.

    Args:
        taskid_* (int): something like 181204020
        name_* (str): something like '3C295'
        beamlist_* (List[int]): something like [0, 1, 2, ..., 9]

    Returns:
        Tuple[bool, str]: True if the pipeline succeeds, informative message
    """
    basedir = '/data/apertif/{}/'.format(taskid_target)
    if not os.path.exists(basedir):
        os.mkdir(basedir)

    logfilepath = os.path.join(basedir, 'apercal.log')

    lib.setup_logger('debug', logfile=logfilepath)
    logger = logging.getLogger(__name__)
    gitinfo = subprocess.check_output('cd ' + os.path.dirname(apercal.__file__) +
                                      '&& git describe --tag; cd', shell=True).strip()
    logger.info("Apercal version: " + gitinfo)

    name_fluxcal = str(name_fluxcal).strip()
    name_polcal = str(name_polcal).strip()
    name_target = str(name_target).strip()

    if not subs_calmodels.is_polarised(name_polcal):
        if subs_calmodels.is_polarised(name_fluxcal):
            logger.debug("Switching polcal and fluxcal because " + name_polcal +
                         " is not polarised")
            name_fluxcal, name_polcal = name_polcal, name_fluxcal
            taskid_fluxcal, taskid_polcal = taskid_polcal, taskid_fluxcal
            beamlist_fluxcal, beamlist_polcal = beamlist_polcal, beamlist_fluxcal
        else:
            logger.debug("Setting polcal to '' since " + self.polcal + " not polarised")
            name_polcal = ""
    else:
        logger.debug("Polcal " + name_polcal + " is polarised, all good")

    def set_files(p):
        """
        Set the basedir, fluxcal, polcal, target properties

        Args:
            p (BaseModule): apercal step object (e.g. prepare)

        Returns:
            None
        """
        p.basedir = basedir
        p.fluxcal = name_fluxcal + ".MS"
        p.polcal = name_polcal + ".MS"
        p.target = name_target + ".MS"

    time_start = time()
    try:
        p0 = prepare()
        set_files(p0)
        p0.prepare_target_beams = ','.join(['{:02d}'.format(beamnr) for beamnr in beamlist_target])
        p0.prepare_date = str(taskid_target)[:6]
        p0.prepare_obsnum_fluxcal = str(taskid_fluxcal)[-3:]
        p0.prepare_obsnum_polcal = str(taskid_polcal)[-3:]
        p0.prepare_obsnum_target = str(taskid_target)[-3:]

        p0.go()

        p1 = preflag()
        set_files(p1)

        p1.go()

        p2 = ccal()
        set_files(p2)
        p2.go()

        p3 = convert()
        set_files(p3)
        #p3.go()

        time_end = time()
        msg = "Apercal finished after " + timedelta(seconds=time()-time_start)
        logger.info(msg)
        return True, msg
    except Exception as e:
        time_end = time()
        msg = "Apercal threw an error after " + timedelta(seconds=time()-time_start)
        logger.exception(msg)
        return False, msg + '\n' + str(e) + '\n' + "Check log at " + logfilepath
