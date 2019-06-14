#!/usr/bin/env python

from __future__ import print_function

from apercal.modules.prepare import prepare
from apercal.modules.split import split
from apercal.modules.preflag import preflag
from apercal.modules.ccal import ccal
#from dataqa.crosscal.crosscal_plots import make_all_ccal_plots
from apercal.modules.scal import scal
from apercal.modules.continuum import continuum
from apercal.modules.line import line
from apercal.subs.managefiles import director
from apercal.modules.convert import convert
from apercal.subs import calmodels as subs_calmodels
from apercal.exceptions import ApercalException
import socket
import apercal
import os
import subprocess
import apercal.libs.lib as lib
from apercal.subs.msutils import get_source_name
import logging
from time import time
from datetime import timedelta
import pymp


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
                           steps=None, configfilename=None):
    """
    Trigger the start of a fluxcal pipeline. Returns when pipeline is done.
    Example for taskid, name, beamnr: (190108926, '3C147_36', 36)
    Fluxcals and polcals can be specified in the wrong order, if the polcal is not polarised
    they will be flipped.
    If both polcals and fluxcals are set, they should both be the same length.

    Args:
        targets (Tuple[int, str, List[int]]): taskid, name, list of beamnrs
        fluxcals (List[Tuple[int, str, int]]): fluxcals: taskid, name, beamnr
        polcals (List[Tuple[int, str, int]]): polcals: taskid, name, beamnr (can be None)
        dry_run (bool): interpret arguments, do not actually run pipeline
        basedir (str): base directory; if not specified will be /data/apertif/{target_taskid}
        flip_ra (bool): flip RA (for old measurement sets where beamweights were flipped)
        steps (List[str]): list of steps to perform
        configfilename (str): Custom configfile (should be full path for now)

    Returns:
        Tuple[Dict[int, List[str]], str], str: Tuple of a dict, the formatted runtime, and possibly
                                          an exception. The dict
                                          contains beam numbers (ints) as keys, a list of failed
                                          steps as values. Failed is defined here as 'threw an
                                          exception', only for target steps. Please also read logs.
    """
    if steps is None:
        steps = ["prepare", "preflag", "ccal",
                 "convert", "scal", "continuum", "line"]

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

    status = pymp.shared.dict({beamnr: [] for beamnr in beamlist_target})

    if fluxcals:
        name_fluxcal = str(fluxcals[0][1]).strip().split('_')[0].upper()
    else:
        name_fluxcal = ''
    if polcals:
        name_polcal = str(polcals[0][1]).strip().split('_')[0].upper()
    else:
        name_polcal = ''
    name_target = str(name_target).strip()  # .upper()

    # If both fluxcal and polcal polarized, remove polcal
    if subs_calmodels.is_polarised(name_polcal) and subs_calmodels.is_polarised(name_fluxcal):
        name_polcal = ""

    if (fluxcals and fluxcals != '') and (polcals and polcals != ''):
        assert(len(fluxcals) == len(polcals))

    # Exchange polcal and fluxcal if specified in the wrong order
    if not subs_calmodels.is_polarised(name_polcal) and name_polcal != '':
        if subs_calmodels.is_polarised(name_fluxcal):
            logger.debug("Switching polcal and fluxcal because " + name_polcal +
                         " is not polarised")
            fluxcals, polcals = polcals, fluxcals
            name_polcal = str(polcals[0][1]).strip()
        else:
            logger.debug("Setting polcal to '' since " +
                         name_polcal + " is not polarised")
            name_polcal = ""
    elif name_polcal != '':
        logger.debug("Polcal " + name_polcal + " is polarised, all good")

    def name_to_ms(name):
        if not name:
            return ''
        elif '3C' in name:
            return name.upper().strip().split('_')[0] + '.MS'
        else:
            return name + '.MS'

    def set_files(p):
        """
        Set the basedir, fluxcal, polcal, target properties

        Args:
            p (BaseModule): apercal step object (e.g. prepare)

        Returns:
            None
        p.basedir = basedir
        p.fluxcal = name_to_ms(name_fluxcal)
        p.polcal = name_to_ms(name_polcal)
        p.target = name_to_ms(name_target)
        """

        # debug_msg = """
        # p.basedir = basedir = {0};
        # p.fluxcal = name_to_ms(name_fluxcal) = {1};
        # p.polcal = name_to_ms(name_polcal) = {2};
        # p.target = name_to_ms(name_target) = {3};
        # """.format(basedir, name_to_ms(name_fluxcal), name_to_ms(name_polcal), name_to_ms(name_target))
        # logger.debug(debug_msg)

    beamnrs_fluxcal = [f[2] for f in fluxcals]
    if len(fluxcals) > 1:
        # Check every target beam has a fluxcal beam
        for beamnr_target in beamlist_target:
            assert(beamnr_target in beamnrs_fluxcal)

    time_start = time()
    try:
        # =======
        # Prepare
        # =======

        # Prepare fluxcals
        for (taskid_fluxcal, name_fluxcal, beamnr_fluxcal) in fluxcals:
            p0 = prepare(file_=configfilename)
            #p0.basedir = basedir
            set_files(p0)
            p0.prepare_flip_ra = flip_ra
            # the following two need to be empty strings for prepare
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
                    logger.warning("Prepare failed for fluxcal " +
                                   str(taskid_fluxcal) + " beam " + str(beamnr_fluxcal))
                    logger.exception(e)

        # Prepare polcals
        if name_polcal != '':
            for (taskid_polcal, name_polcal, beamnr_polcal) in polcals:
                p0 = prepare(file_=configfilename)
                #p0.basedir = basedir
                set_files(p0)
                p0.prepare_flip_ra = flip_ra
                # the following two need to be empty strings for prepare
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
        p0 = prepare(file_=configfilename)
        #p0.basedir = basedir
        set_files(p0)
        p0.prepare_flip_ra = flip_ra
        # the following two need to be empty strings for prepare
        p0.fluxcal = ''
        p0.polcal = ''
        #p0.target = name_to_ms(name_target)
        p0.prepare_date = str(taskid_target)[:6]
        p0.prepare_obsnum_target = validate_taskid(taskid_target)
        for beamnr in beamlist_target:
            p0.prepare_target_beams = ','.join(
                ['{:02d}'.format(beamnr) for beamnr in beamlist_target])
            if "prepare" in steps and not dry_run:
                try:
                    p0.go()
                except Exception as e:
                    logger.warning("Prepare failed for target " +
                                   str(taskid_target) + " beam " + str(beamnr))
                    logger.exception(e)
                    status[beamnr] += ['prepare']

        # =====
        # Split
        # =====

        # Splitting a small chunk of data for quicklook pipeline
        # at the moment it all relies on the target beams
        # what if there are more calibrator than target beams-> realistic?
        s0 = split(file_=configfilename)
        set_files(s0)
        for beamnr in beamlist_target:
            s0.beam = "{:02d}".format(beamnr)
            if "split" in steps and not dry_run:
                try:
                    s0.go()
                except Exception as e:
                    logger.warning("Split failed for {0} beam {1}".format(
                        str(taskid_target), str(beamnr)))
                    logger.exception(e)
                    # not sure if following line is necessary
                    status[beamnr] += ['split']

        # =======
        # Preflag
        # =======

        # keep a record of the parallalised step in the main log file
        logger.info("Running preflag")
        start_time_preflag = time()

        # In order to run in parallel, the bandpass table needs to exists
        # doing it here is not elegant but requires the least amount of changes
        # to preflage
        with pymp.Parallel(10) as p:
            for beam_index in p.range(len(beamlist_target)):
                beamnr = beamlist_target[beam_index]
                # individual logfiles for each process
                logfilepath = os.path.join(
                    basedir, 'apercal{:02d}.log'.format(beamnr))
                lib.setup_logger('debug', logfile=logfilepath)
                logger = logging.getLogger(__name__)

                logger.debug("Starting logfile for beam " + str(beamnr))
                p1 = preflag(filename=configfilename)
                p1.paramfilename = 'param_{:02d}.npy'.format(beamnr)
                p1.basedir = basedir
                p1.fluxcal = ''
                p1.polcal = ''
                p1.target = name_to_ms(name_fluxcal)

                p1.beam = "{:02d}".format(beamnr)
                p1.preflag_targetbeams = "{:02d}".format(beamnr)
                if "preflag" in steps and not dry_run:
                    try:
                        bandpass_start_time = time()
                        logger.info("Running aoflagger bandpass for flux calibrator {0} in beam {1}".format(
                            p1.target, p1.beam))
                        director(
                            p1, 'rm', basedir + '/param_{:02d}.npy'.format(beamnr), ignore_nonexistent=True)
                        p1.go()
                        # director(p1, 'rm', basedir + '/param.npy',
                        #         ignore_nonexistent=True)
                        p1.aoflagger_bandpass()
                    except Exception as e:
                        logger.warning("Running aoflagger bandpass for flux calibrator {0} in beam {1} ... Failed ({2:.0f}s)".format(
                            p1.target, p1.beam, time() - bandpass_start_time))
                        logger.exception(e)
                        status[beamnr] += ['preflag_bandpass']
                    else:
                        logger.info("Running aoflagger bandpass for flux calibrator {0} in beam {1} ... Done ({2:.0f}s)".format(
                            p1.target, p1.beam, time() - bandpass_start_time))
        
        # # Flag fluxcal (pretending it's a target)
        # p1 = preflag(filename=configfilename)
        # # remove next line in final version
        # p1.preflag_aoflagger_version = 'local'
        # p1.basedir = basedir
        # p1.fluxcal = ''
        # p1.polcal = ''
        # p1.target = name_to_ms(name_fluxcal)
        # for beamnr in beamlist_target:
        #     p1.beam = "{:02d}".format(beamnr)
        #     p1.preflag_targetbeams = "{:02d}".format(beamnr)
        #     if "preflag" in steps and not dry_run:
        #         logging.info("Running preflag for flux calibrator {0} in beam {1}".format(
        #             p1.target, p1.beam))
        #         preflag_flux_cal_start_time = time()
        #         try:
        #             director(p1, 'rm', basedir + '/param.npy',
        #                      ignore_nonexistent=True)
        #             p1.go()
        #         except Exception as e:
        #             logging.warning("Running preflag for flux calibrator {0} in beam {1} ... failed ({2:.0f}s)".format(
        #                 p1.target, p1.beam, time() - preflag_flux_cal_start_time))
        #             logger.exception(e)
        #             status[beamnr] += ['preflag']
        #         else:
        #             logging.info("Running preflag for flux calibrator {0} in beam {1} ... Done ({2:.0f}s)".format(
        #                 p1.target, p1.beam, time() - preflag_flux_cal_start_time))

        # Flag fluxcal (pretending it's a target, parallelised version)
        # 5 in parallel
        with pymp.Parallel(5) as p:
            for beam_index in p.range(len(beamlist_target)):
                beamnr = beamlist_target[beam_index]

                # individual logfiles for each process
                logfilepath = os.path.join(
                    basedir, 'apercal{:02d}.log'.format(beamnr))
                lib.setup_logger('debug', logfile=logfilepath)
                logger = logging.getLogger(__name__)

                logger.debug("Starting logfile for beam " + str(beamnr))

                try:
                    p1 = preflag(filename=configfilename)
                    p1.paramfilename = 'param_{:02d}.npy'.format(beamnr)
                    p1.basedir = basedir
                    p1.fluxcal = ''
                    p1.polcal = ''
                    p1.target = name_to_ms(name_fluxcal)
                    p1.beam = "{:02d}".format(beamnr)
                    p1.preflag_targetbeams = "{:02d}".format(beamnr)
                    if beam_index < 2:
                        p1.preflag_aoflagger_threads = 9
                    else:
                        p1.preflag_aoflagger_threads = 10
                    if "preflag" in steps and not dry_run:
                        logger.info("Running preflag for flux calibrator {0} in beam {1}".format(
                            p1.target, p1.beam))
                        preflag_flux_cal_start_time = time()
                        director(
                            p1, 'rm', basedir + '/param_{:02d}.npy'.format(beamnr), ignore_nonexistent=True)
                        p1.go()
                        logger.info("Running preflag for flux calibrator {0} in beam {1} ... Done ({2:.0f}s)".format(
                            p1.target, p1.beam, time() - preflag_flux_cal_start_time))
                except Exception as e:
                    logger.warning("Running preflag for flux calibrator {0} in beam {1} ... Failed, but probably because of maximum interval ({2:.0f}s)".format(
                        p1.target, p1.beam, time() - preflag_flux_cal_start_time))
                    logger.exception(e)
                    status[beamnr] += ['preflag']

        # # Flag polcal (pretending it's a target)
        # p1 = preflag(filename=configfilename)
        # # remove next line in final version
        # p1.preflag_aoflagger_version = 'local'
        # p1.basedir = basedir
        # if name_polcal != '':
        #     p1.fluxcal = ''
        #     p1.polcal = ''
        #     p1.target = name_to_ms(name_polcal)
        #     for beamnr in beamlist_target:
        #         p1.beam = "{:02d}".format(beamnr)
        #         p1.preflag_targetbeams = "{:02d}".format(beamnr)
        #         if "preflag" in steps and not dry_run:
        #             logging.info("Running preflag for pol calibrator {0} in beam {1}".format(
        #                 p1.target, p1.beam))
        #             preflag_pol_cal_start_time = time()
        #             try:
        #                 director(p1, 'rm', basedir + '/param.npy',
        #                          ignore_nonexistent=True)
        #                 p1.go()
        #             except Exception as e:
        #                 logging.warning("Running preflag for pol calibrator {0} in beam {1} ... Failed ({2:.0f}s)".format(
        #                     p1.target, p1.beam, time() - preflag_pol_cal_start_time))
        #                 logger.exception(e)
        #             else:
        #                 logging.info("Running preflag for pol calibrator {0} in beam {1} ... Done ({2:.0f}s)".format(
        #                     p1.target, p1.beam, time() - preflag_pol_cal_start_time))

        # Flag polcal (pretending it's a target, parallel version)
        # 5 in parallel
        with pymp.Parallel(5) as p:
            for beam_index in p.range(len(beamlist_target)):
                beamnr = beamlist_target[beam_index]

                # individual logfiles for each process
                logfilepath = os.path.join(
                    basedir, 'apercal{:02d}.log'.format(beamnr))
                lib.setup_logger('debug', logfile=logfilepath)
                logger = logging.getLogger(__name__)

                logger.debug("Starting logfile for beam " + str(beamnr))

                try:
                    p1 = preflag(filename=configfilename)
                    # remove next line in final version
                    p1.preflag_aoflagger_version = 'local'
                    p1.basedir = basedir
                    p1.paramfilename = 'param_{:02d}.npy'.format(beamnr)
                    p1.basedir = basedir
                    if name_polcal != '':
                        p1.fluxcal = ''
                        p1.polcal = ''
                        p1.target = name_to_ms(name_polcal)
                        p1.beam = "{:02d}".format(beamnr)
                        p1.preflag_targetbeams = "{:02d}".format(beamnr)
                        if beam_index < 2:
                            p1.preflag_aoflagger_threads = 9
                        else:
                            p1.preflag_aoflagger_threads = 10
                        if "preflag" in steps and not dry_run:
                            logger.info("Running preflag for pol calibrator {0} in beam {1}".format(
                                p1.target, p1.beam))
                            preflag_pol_cal_start_time = time()
                            director(
                                p1, 'rm', basedir + '/param_{:02d}.npy'.format(beamnr), ignore_nonexistent=True)
                            p1.go()
                            logger.info("Running preflag for pol calibrator {0} in beam {1} ... Done ({2:.0f}s)".format(
                                p1.target, p1.beam, time() - preflag_pol_cal_start_time))
                except Exception as e:
                    logger.warning("Running preflag for pol calibrator {0} in beam {1} ... Failed, but probably because of maximum interval ({2:.0f}s)".format(
                        p1.target, p1.beam, time() - preflag_pol_cal_start_time))
                    logger.exception(e)
                    status[beamnr] += ['preflag']

        # # Flag target
        # p1 = preflag(filename=configfilename)
        # # remove next line in final version
        # p1.preflag_aoflagger_version = 'local'
        # p1.basedir = basedir
        # p1.fluxcal = ''
        # p1.polcal = ''
        # p1.target = name_to_ms(name_target)
        # for beamnr in beamlist_target:
        #     p1.beam = "{:02d}".format(beamnr)
        #     p1.preflag_targetbeams = "{:02d}".format(beamnr)
        #     if "preflag" in steps and not dry_run:
        #         logging.info("Running preflag for target {0} in beam {1}".format(
        #             p1.target, p1.beam))
        #         preflag_target_start_time = time()
        #         try:
        #             director(p1, 'rm', basedir + '/param.npy',
        #                      ignore_nonexistent=True)
        #             p1.go()
        #         except Exception as e:
        #             logging.info("Running preflag for target {0} in beam {1} ... Failed ({2:.0f}s)".format(
        #                 p1.target, p1.beam, time() - preflag_target_start_time))
        #             logger.exception(e)
        #         else:
        #             logging.info("Running preflag for target {0} in beam {1} ... Done ({2:.0f}s)".format(
        #                 p1.target, p1.beam, time() - preflag_target_start_time))

        # Flag target
        # 5 in parallel
        with pymp.Parallel(5) as p:
            for beam_index in p.range(len(beamlist_target)):
                beamnr = beamlist_target[beam_index]

                # individual logfiles for each process
                logfilepath = os.path.join(
                    basedir, 'apercal{:02d}.log'.format(beamnr))
                lib.setup_logger('debug', logfile=logfilepath)
                logger = logging.getLogger(__name__)

                logger.debug("Starting logfile for beam " + str(beamnr))

                try:
                    p1 = preflag(filename=configfilename)
                    # remove next line in final version
                    p1.preflag_aoflagger_version = 'local'
                    p1.paramfilename = 'param_{:02d}.npy'.format(beamnr)
                    p1.basedir = basedir
                    p1.fluxcal = ''
                    p1.polcal = ''
                    p1.target = name_to_ms(name_target)
                    p1.beam = "{:02d}".format(beamnr)
                    p1.preflag_targetbeams = "{:02d}".format(beamnr)
                    if beam_index < 2:
                        p1.preflag_aoflagger_threads = 9
                    else:
                        p1.preflag_aoflagger_threads = 10
                    if "preflag" in steps and not dry_run:
                        logger.info("Running preflag for target {0} in beam {1}".format(
                            p1.target, p1.beam))
                        preflag_target_start_time = time()
                        director(
                            p1, 'rm', basedir + '/param_{:02d}.npy'.format(beamnr), ignore_nonexistent=True)
                        p1.go()
                        logger.info("Running preflag for target {0} in beam {1} ... Done ({2:.0f}s)".format(
                            p1.target, p1.beam, time() - preflag_target_start_time))
                except Exception as e:
                    logger.info("Running preflag for target {0} in beam {1} ... Failed ({2:.0f}s)".format(
                        p1.target, p1.beam, time() - preflag_target_start_time))
                    logger.exception(e)
                    status[beamnr] += ['preflag']

        # keep a record of the parallalised step in the main log file
        logfilepath = os.path.join(basedir, 'apercal.log'.format(beamnr))
        lib.setup_logger('debug', logfile=logfilepath)
        logger = logging.getLogger(__name__)

        logger.info("Running preflag ... Done ({0:.0f}s)".format(
            time() - start_time_preflag))

        # ===============
        # Crosscal
        # ===============

        # keep a record of the parallalised step in the main log file
        logger.info("Running crosscal")
        start_time_crosscal = time()

        if len(fluxcals) == 1 and fluxcals[0][-1] == 0 and len(beamlist_target) > 1:
            raise ApercalException(
                "Sorry, one fluxcal is not supported anymore at the moment")

        with pymp.Parallel(10) as p:
            for beam_index in p.range(len(beamlist_target)):
                beamnr = beamlist_target[beam_index]

                logfilepath = os.path.join(
                    basedir, 'apercal{:02d}.log'.format(beamnr))
                lib.setup_logger('debug', logfile=logfilepath)
                logger = logging.getLogger(__name__)

                logger.debug("Starting logfile for beam " + str(beamnr))
                try:
                    p2 = ccal(file_=configfilename)
                    p2.paramfilename = 'param_{:02d}.npy'.format(beamnr)
                    set_files(p2)
                    p2.beam = "{:02d}".format(beamnr)
                    p2.crosscal_transfer_to_target_targetbeams = "{:02d}".format(
                        beamnr)
                    if "ccal" in steps and not dry_run:
                        director(
                            p2, 'rm', basedir + '/param_{:02d}.npy'.format(beamnr), ignore_nonexistent=True)
                        p2.go()
                except Exception as e:
                    # Exception was already logged just before
                    logger.warning(
                        "Failed beam {}, skipping that from crosscal".format(beamnr))
                    logger.exception(e)
                    status[beamnr] += ['crosscal']
        
        # keep a record of the parallalised step in the main log file
        logfilepath = os.path.join(basedir, 'apercal.log'.format(beamnr))
        lib.setup_logger('debug', logfile=logfilepath)
        logger = logging.getLogger(__name__)

        logger.info("Running crosscal ... Done ({0:.0f}s)".format(
            time() - start_time_crosscal))


        # =======
        # Convert
        # =======

        # keep a record of the parallalised step in the main log file
        logger.info("Running convert")
        start_time_convert = time()

        # 5 threads to not hammer the disks too much, convert is only IO
        with pymp.Parallel(5) as p:
            for beam_index in p.range(len(beamlist_target)):
                beamnr = beamlist_target[beam_index]

                logfilepath = os.path.join(
                    basedir, 'apercal{:02d}.log'.format(beamnr))
                lib.setup_logger('debug', logfile=logfilepath)
                logger = logging.getLogger(__name__)

                try:
                    p3 = convert(file_=configfilename)
                    p3.paramfilename = 'param_{:02d}.npy'.format(beamnr)
                    set_files(p3)
                    p3.beam = "{:02d}".format(beamnr)
                    p3.convert_targetbeams = "{:02d}".format(beamnr)
                    if "convert" in steps and not dry_run:
                        director(
                            p3, 'rm', basedir + '/param_{:02d}.npy'.format(beamnr), ignore_nonexistent=True)
                        p3.go()
                        director(
                            p3, 'rm', basedir + '/param_{:02d}.npy'.format(beamnr), ignore_nonexistent=True)
                except Exception as e:
                    logger.warning(
                        "Failed beam {}, skipping that from convert".format(beamnr))
                    logger.exception(e)
                    status[beamnr] += ['convert']

        # keep a record of the parallalised step in the main log file
        logfilepath = os.path.join(basedir, 'apercal.log'.format(beamnr))
        lib.setup_logger('debug', logfile=logfilepath)
        logger = logging.getLogger(__name__)

        logger.info("Running convert ... Done ({0:.0f}s)".format(
            time() - start_time_convert))


        # ===================
        # Selfcal + Continuum
        # ===================

        # keep a record of the parallalised step in the main log file
        logger.info("Running selfcal and continuum")
        start_time_selfcal_continuum = time()

        with pymp.Parallel(10) as p:
            for beam_index in p.range(len(beamlist_target)):
                beamnr = beamlist_target[beam_index]

                logfilepath = os.path.join(
                    basedir, 'apercal{:02d}.log'.format(beamnr))
                lib.setup_logger('debug', logfile=logfilepath)
                logger = logging.getLogger(__name__)

                try:
                    p4 = scal(file_=configfilename)
                    p4.paramfilename = 'param_{:02d}.npy'.format(beamnr)
                    p4.basedir = basedir
                    p4.beam = "{:02d}".format(beamnr)
                    p4.target = name_target + '.mir'
                    if "scal" in steps and not dry_run:
                        p4.go()
                except Exception as e:
                    # Exception was already logged just before
                    logger.warning(
                        "Failed beam {}, skipping that from scal".format(beamnr))
                    logger.exception(e)
                    status[beamnr] += ['scal']

                try:
                    p5 = continuum(file_=configfilename)
                    p5.paramfilename = 'param_{:02d}.npy'.format(beamnr)
                    p5.basedir = basedir
                    p5.beam = "{:02d}".format(beamnr)
                    p5.target = name_target + '.mir'
                    if "continuum" in steps and not dry_run:
                        p5.go()
                except Exception as e:
                    # Exception was already logged just before
                    logger.warning(
                        "Failed beam {}, skipping that from continuum".format(beamnr))
                    logger.exception(e)
                    status[beamnr] += ['continuum']
        
        # keep a record of the parallalised step in the main log file
        logfilepath = os.path.join(basedir, 'apercal.log'.format(beamnr))
        lib.setup_logger('debug', logfile=logfilepath)
        logger = logging.getLogger(__name__)

        logger.info("Running selfcal and continuum ... Done ({0:.0f}s)".format(
            time() - start_time_selfcal_continuum))


        # ====
        # Line
        # ====

        logfilepath = os.path.join(basedir, 'apercal.log')
        lib.setup_logger('debug', logfile=logfilepath)
        # keep a record of the parallalised step in the main log file
        logger.info("Running line")
        start_time_line = time()

        for beamnr in beamlist_target:
            try:
                p6 = line(file_=configfilename)
                if beamnr not in p6.line_beams:
                    logger.debug(
                        "Skipping line imaging for beam {}".format(beamnr))
                    continue
                p6.basedir = basedir
                p6.beam = "{:02d}".format(beamnr)
                p6.target = name_target + '.mir'
                if "line" in steps and not dry_run:
                    p6.go()
            except Exception as e:
                # Exception was already logged just before
                logger.warning(
                    "Failed beam {}, skipping that from line".format(beamnr))
                logger.exception(e)
                status[beamnr] += ['line']

        # keep a record of the parallalised step in the main log file
        logfilepath = os.path.join(basedir, 'apercal.log'.format(beamnr))
        lib.setup_logger('debug', logfile=logfilepath)
        logger = logging.getLogger(__name__)

        logger.info("Running line ... Done ({0:.0f}s)".format(
            time() - start_time_line))


        if "ccalqa" in steps and not dry_run:
            logger.info("Starting crosscal QA plots")
            try:
                make_all_ccal_plots(
                    taskid_target, name_fluxcal.upper().strip().split('_')[0])
            except Exception as e:
                logger.warning("Failed crosscal QA plots")
                logger.exception(e)
            logger.info("Done with crosscal QA plots")

        status = status.copy()  # Convert pymp shared dict to a normal one
        msg = "Apercal finished after " + \
            str(timedelta(seconds=time() - time_start))
        logger.info(msg)
        return status, str(timedelta(seconds=time() - time_start)), None
    except Exception as e:
        msg = "Apercal threw an error after " + \
            str(timedelta(seconds=time() - time_start))
        logger.exception(msg)
        return status, str(timedelta(seconds=time() - time_start)), str(e)
