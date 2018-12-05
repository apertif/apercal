#!/usr/bin/env python

from __future__ import print_function

import matplotlib as mpl
from apercal.modules.prepare import prepare
from apercal.modules.preflag import preflag
from apercal.modules.ccal import ccal
import apercal
import os
import subprocess
import apercal.libs.lib as lib
from apercal.subs.msutils import get_source_name
import logging
import sys

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
        bool: True if apercal started successfully
    """
    basedir = '/data/apertif/{}/'.format(taskid_target)
    if not os.path.exists(basedir):
        os.mkdir(basedir)

    lib.setup_logger('debug', logfile=os.path.join(basedir, 'apercal.log'))
    logger = logging.getLogger(__name__)
    gitinfo = subprocess.check_output('cd ' + os.path.dirname(apercal.__file__) +
                                      '&& git describe --tag; cd', shell=True).strip()
    logger.info("Apercal version: " + gitinfo)

    p0 = prepare()
    p0.basedir = basedir
    p0.fluxcal = name_fluxcal + ".MS"
    p0.polcal = name_polcal + ".MS"
    p0.target = name_target + ".MS"

    p0.prepare_target_beams = ','.join(['{:02d}'.format(beamnr) for beamnr in beamlist_target])
    p0.prepare_date = str(taskid_target)[:6]
    p0.prepare_obsnum_fluxcal = str(taskid_fluxcal)[-3:]
    p0.prepare_obsnum_polcal = str(taskid_polcal)[-3:]
    p0.prepare_obsnum_target = str(taskid_target)[-3:]

    p0.go()

    p1 = preflag()
    p1.fluxcal = p0.fluxcal
    p1.polcal = p0.polcal
    p1.target = p0.target

    p1.go()

    return True
