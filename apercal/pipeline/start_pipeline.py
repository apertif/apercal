#!/usr/bin/env python

from __future__ import print_function

import matplotlib as mpl
from apercal.modules.prepare import prepare
from apercal.modules.preflag import preflag
from apercal.modules.ccal import ccal
from apercal.modules.scal import scal
from apercal.modules.continuum import continuum
from apercal.subs.managefiles import director
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


def start_apercal_pipeline(targets, fluxcals, polcals, dry_run=False, basedir=None, flip_ra=False,
                           steps=["prepare", "preflag", "ccal", "convert", "scal", "continuum"]):
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
        flip_ra (bool): flip RA (for old measurement sets where beamweights were flipped)

    Returns:
        Tuple[bool, str]: True if the pipeline succeeds, informative message
    """
    (taskid_target, name_target, beamlist_target) = targets

    if not basedir:
        basedir = '/data/apertif/{}/'.format(taskid_target)
    elif len(basedir) > 0 and basedir[-1] != '/':
        basedir = basedir + '/'
    if not os.path.exists(basedir):
        os.mkdir(basedir)

    logfilepath = os.path.join(basedir, 'apercal.log')

    lib.setup_logger('debug', logfile=logfilepath)
    logger = logging.getLogger(__name__)
    gitinfo = subprocess.check_output('cd ' + os.path.dirname(apercal.__file__) +
                                      '&& git describe --tag; cd', shell=True).strip()
    logger.info("Apercal version: " + gitinfo)

    logger.debug("start_apercal called with arguments targets={}; fluxcals={}; polcals={}".format(
                  targets, fluxcals, polcals))
    logger.debug("steps = {}".format(steps))

    name_fluxcal = str(fluxcals[0][1]).strip().split('_')[0]
    if polcals:
        name_polcal = str(polcals[0][1]).strip().split('_')[0]
    else:
        name_polcal = ''
    name_target = str(name_target).strip()

    # Exchange polcal and fluxcal if specified in the wrong order
    if not subs_calmodels.is_polarised(name_polcal) and name_polcal != '':
        if subs_calmodels.is_polarised(name_fluxcal):
            logger.debug("Switching polcal and fluxcal because " + name_polcal +
                         " is not polarised")
            fluxcals, polcals = polcals, fluxcals
            name_polcal = str(polcals[0][1]).strip()
        else:
            logger.debug("Setting polcal to '' since " + name_polcal + " is not polarised")
            name_polcal = ""
    elif name_polcal != '':
        logger.debug("Polcal " + name_polcal + " is polarised, all good")

    def name_to_ms(name):
        if not name:
            return ''
        else:
            return name.upper().strip().split('_')[0] + '.MS'

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

    beamnrs_fluxcal = [f[2] for f in fluxcals]
    if len(fluxcals) > 1:
        # Check every target beam has a fluxcal beam
        for beamnr_target in beamlist_target:
            assert(beamnr_target in beamnrs_fluxcal)

    time_start = time()
    try:
        # Prepare fluxcals
        for (taskid_fluxcal, name_fluxcal, beamnr_fluxcal) in fluxcals:
            # director(p0, 'rm', basedir+'/param.npy', ignore_nonexistent=True)
            p0 = prepare()
            p0.basedir = basedir
            p0.prepare_flip_ra = flip_ra
            p0.fluxcal = ''
            p0.polcal = ''
            p0.target = name_to_ms(name_fluxcal)
            p0.prepare_target_beams = str(beamnr_fluxcal)
            p0.prepare_date = str(taskid_fluxcal)[:6]
            p0.prepare_obsnum_target = validate_taskid(taskid_fluxcal)
            if "prepare" in steps and not dry_run:
                try:
                    p0.go()
                except Exception as e:
                    logger.warning("Prepare failed for fluxcal " + str(taskid_fluxcal) + " beam " + str(beamnr_fluxcal))
                    logger.exception(e)

        # Prepare polcals
        if name_polcal != '':
            for (taskid_polcal, name_polcal, beamnr_polcal) in polcals:
                p0 = prepare()
                p0.basedir = basedir
                p0.prepare_flip_ra = flip_ra
                p0.fluxcal = ''
                p0.polcal = ''
                p0.target = name_to_ms(name_polcal)
                p0.prepare_target_beams = str(beamnr_polcal)
                p0.prepare_date = str(taskid_polcal)[:6]
                p0.prepare_obsnum_target = validate_taskid(taskid_polcal)
                if "prepare" in steps and not dry_run:
                    try:
                        p0.go()
                    except Exception as e:
                        logger.warning(
                            "Prepare failed for polcal " + str(taskid_polcal) + " beam " + str(beamnr_polcal))
                        logger.exception(e)

        # Prepare target
        p0 = prepare()
        p0.basedir = basedir
        p0.prepare_flip_ra = flip_ra
        p0.fluxcal = ''
        p0.polcal = ''
        p0.target = name_to_ms(name_target)
        p0.prepare_date = str(taskid_target)[:6]
        p0.prepare_obsnum_target = validate_taskid(taskid_target)
        for beamnr in beamlist_target:
            p0.prepare_target_beams = ','.join(['{:02d}'.format(beamnr) for beamnr in beamlist_target])
            if "prepare" in steps and not dry_run:
                try:
                    p0.go()
                except Exception as e:
                    logger.warning("Prepare failed for target " + str(taskid_target) + " beam " + str(beamnr))
                    logger.exception(e)

        # Flag fluxcal (pretending it's a target)
        p1 = preflag()
        p1.basedir = basedir
        director(p0, 'rm', basedir + '/param.npy', ignore_nonexistent=True)
        p1.fluxcal = ''
        p1.polcal = ''
        p1.target = name_to_ms(name_fluxcal)
        p1.beam = "{:02d}".format(beamlist_target[0])
        if "prepare" in steps and not dry_run:
            p1.go()

        # Flag polcal (pretending it's a target)
        p1 = preflag()
        p1.basedir = basedir
        director(p0, 'rm', basedir + '/param.npy', ignore_nonexistent=True)
        if name_polcal != '':
            p1.fluxcal = ''
            p1.polcal = ''
            p1.target = name_to_ms(name_polcal)
            p1.beam = "{:02d}".format(beamlist_target[0])
            if "prepare" in steps and not dry_run:
                p1.go()

        p1 = preflag()
        p1.basedir = basedir
        director(p0, 'rm', basedir + '/param.npy', ignore_nonexistent=True)
        # Flag target
        p1.fluxcal = ''
        p1.polcal = ''
        p1.target = name_to_ms(name_target)
        p1.beam = "{:02d}".format(beamlist_target[0])
        if "preflag" in steps and not dry_run:
            p1.go()

        if len(fluxcals) == 1 and fluxcals[0][-1] == 0:
            p2 = ccal()
            set_files(p2)
            if "preflag" in steps and not dry_run:
                p2.go()
        else:
            for beamnr in beamlist_target:
                try:
                    p2 = ccal()
                    p2.basedir = basedir
                    director(p2, 'rm', basedir + '/param.npy', ignore_nonexistent=True)
                    p2.fluxcal = name_to_ms(name_fluxcal)
                    p2.polcal = name_to_ms(name_polcal)
                    p2.target = name_to_ms(name_target)
                    p2.beam = "{:02d}".format(beamnr)
                    p2.crosscal_transfer_to_target_targetbeams = "{:02d}".format(beamnr)
                    if "preflag" in steps and not dry_run:
                        p2.go()
                except Exception as e:
                    # Exception was already logged just before
                    logger.warning("Failed beam {}, skipping that from crosscal".format(beamnr))
                    logger.exception(e)

        p3 = convert()
        set_files(p3)
        if "convert" in steps and not dry_run:
            p3.go()

        director(p3, 'rm', basedir + '/param.npy', ignore_nonexistent=True)
        for beamnr in beamlist_target:
            try:
                p4 = scal()
                p4.basedir = basedir
                p4.beam = "{:02d}".format(beamnr)
                p4.target = name_target + '.mir'
                if "scal" in steps and not dry_run:
                    p4.go()
            except Exception as e:
                # Exception was already logged just before
                logger.warning("Failed beam {}, skipping that from scal".format(beamnr))
                logger.exception(e)

        for beamnr in beamlist_target:
            try:
                p5 = continuum()
                p5.basedir = basedir
                p5.beam = "{:02d}".format(beamnr)
                p5.target = name_target + '.mir'
                if "scal" in steps and not dry_run:
                    p5.go()
            except Exception as e:
                # Exception was already logged just before
                logger.warning("Failed beam {}, skipping that from continuum".format(beamnr))
                logger.exception(e)

        time_end = time()
        msg = "Apercal finished after " + str(timedelta(seconds=time() - time_start))
        logger.info(msg)
        return True, msg
    except Exception as e:
        time_end = time()
        msg = "Apercal threw an error after " + str(timedelta(seconds=time() - time_start))
        logger.exception(msg)
        return False, msg + '\n' + str(e) + '\n' + "Check log at " + socket.gethostname() + ':' + logfilepath
