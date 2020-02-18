#!/usr/bin/python2

"""
Template for a script that can be used to manually process
Apertif Imaging Survey data with the full Apercal pipeline.

This script can run the pipeline and the QA if chosen.
It can be used for any kind of testing and processing.
Note that it does not allow ingest of data

"""

import time
import subprocess
import logging
import apercal.libs.lib as lib
from apercal.pipeline.start_pipeline import start_apercal_pipeline
from dataqa.run_qa import run_triggered_qa
import os
import socket


# Main Settings
# =============
#
# Adjust the following settings

# Provide the target information following the example below
# pattern is (taskid, field name, list of beams)
targets = (191006041, 'S1259+5550', [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])

# Provide the flux and polcal calibrator information following the example below
# pattern is [[calibrator taskid of first beam, obs name, first beam], [calibrator taskid of second beam, obs name, second beam] ...]
fluxcals = [[191005001, '3C196_0', 0], [191005002, '3C196_1', 1], [191005003, '3C196_2', 2], [191005004, '3C196_3', 3], [191005005, '3C196_4', 4],
            [191005006, '3C196_5', 5], [191005007, '3C196_6', 6], [191005008, '3C196_7', 7], [191005009, '3C196_8', 8], [191005010, '3C196_9', 9]]
polcals = [[191006001, '3C138_0', 0], [191006002, '3C138_1', 1], [191006003, '3C138_2', 2], [191006004, '3C138_3', 3], [191006005, '3C138_4', 4],
           [191006006, '3C138_5', 5], [191006007, '3C138_6', 6], [191006008, '3C138_7', 7], [191006009, '3C138_8', 8], [191006010, '3C138_9', 9]]

# set the location of where the data should go, including the taskid
# example: "/data/<user>/taskid"
basedir = None

# turn on/off running apercal and dataqa
do_apercal = True
do_qa = True

# Optional settings:
# ==================
#
# The following settings only have to be adjusted if necessary

# set the location of the configfile for Apercal
# if None, the default is used
configfile = None

# Select steps for the pipeline
# if None, all steps are executed
steps = None

# Select steps for the QA pipeline
# if None, all steps are executed
steps_qa = None


# Nothing to change below
# =======================
def run_manual_processing():
    """Function to run Apercal and QA"""

    # make sure a use base directory
    if basedir is None:
        print("ERROR: No basedir specified. Abort.")
        return -1

    start_time = time.time()

    host_name = socket.gethostname()

    cwd = os.getcwd()

    name_fluxcal = str(fluxcals[0][1]).strip().split('_')[0].upper()

    (task_id, name_target, beamlist_target) = targets

    logfile = os.path.join(cwd, "{0}_{1}_apercal_qa.log".format(
        task_id, host_name))

    # Setting up log file
    lib.setup_logger('debug', logfile=logfile)
    logger = logging.getLogger(__name__)

    if do_apercal:
        logger.info("Running apercal manually")
        logger.info(
            "When apercal runs, the logging information will be in the apercal log")

        logger.info("Using task id: {0}".format(task_id))
        logger.info("target = {}".format(str(targets)))
        logger.info("flux_cal = {}".format(str(fluxcals)))
        logger.info("pol_cal = {}".format(str(polcals)))

        # logger.info("Steps: {}".format(str(steps)))

        try:
            start_time = time.time()
            logger.info('Running apercal')
            # return_msg = start_apercal_pipeline(
            # targets, fluxcals, polcals, basedir=basedir, steps=steps, configfilename=configfile)
            return_msg = start_apercal_pipeline(
                targets, fluxcals, polcals, basedir=basedir, steps=steps, configfilename=configfile)
            # return_msg = start_apercal_pipeline(
            #     targets, fluxcals, polcals, steps=steps)
        except Exception as e:
            lib.setup_logger('debug', logfile=logfile)
            logger = logging.getLogger(__name__)
            logger.warning("Running apercal failed ({0:.3f}h)".format(
                (time.time() - start_time)/3600.))
            logger.warning(return_msg)
            logger.exception(e)
        else:
            lib.setup_logger('debug', logfile=logfile)
            logger = logging.getLogger(__name__)
            logger.info("Running apercal ... Done ({0:.3f}h)".format(
                (time.time() - start_time)/3600.))

    if do_qa:
        logger.info("Running QA manually")
        logger.info(
            "When apercal runs, the logging information will be in the apercal log")

        logger.info("Using task id: {0}".format(task_id))
        logger.info("target = {}".format(str(targets)))
        logger.info("flux_cal = {}".format(str(fluxcals)))
        logger.info("pol_cal = {}".format(str(polcals)))

        logger.info("Running all QA steps")
        try:
            start_time = time.time()
            logger.info('Running QA')
            return_msg = run_triggered_qa(
                targets, fluxcals, polcals, osa="", basedir=os.path.dirname(basedir), steps=steps_qa)
        except Exception as e:
            lib.setup_logger('debug', logfile=logfile)
            logger = logging.getLogger(__name__)
            logger.warning("Running QA failed ({0:.3f}h)".format(
                (time.time() - start_time)/3600.))
            logger.warning(return_msg)
            logger.exception(e)
        else:
            lib.setup_logger('debug', logfile=logfile)
            logger = logging.getLogger(__name__)
            logger.info("Running QA ... Done ({0:.3f}h)".format(
                (time.time() - start_time)/3600.))


if __name__ == "__main__":
    run_manual_processing()
