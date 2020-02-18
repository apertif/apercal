#!/usr/bin/python2

"""
Template for a script that can be used to manually process
Apertif Imaging Survey data with the full Apercal pipeline.

Only use this script if you want to manual process imaging data
because the triggered pipeline is not available

In order to process all 40 beams of a taskid instead of the triggered
pipeline, four versions of this script have to be created: one for each
happili node and each covering 10 beams

"""

import time
import subprocess
import logging
import apercal.libs.lib as lib
from apercal.pipeline.start_pipeline import start_apercal_pipeline
from dataqa.run_qa import run_triggered_qa
from apergest import apergest
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

# turn on/off running apercal, dataqa and apergest
# by default Apergest is turned off
do_apercal = True
do_qa = True
do_apergest = False

# Optional settings:
# ==================
#
# The following settings only have to be adjusted if necessary

# set the location of the configfile for Apercal
# if None, the default is used
configfile = None

# Nothing to change below
# =======================


def run_manual_processing():
    """Function to run Apercal, QA and Apergest"""

    start_time = time.time()

    host_name = socket.gethostname()

    cwd = os.getcwd()

    host_name = socket.gethostname()

    name_fluxcal = str(fluxcals[0][1]).strip().split('_')[0].upper()

    (task_id, name_target, beamlist_target) = targets

    logfile = os.path.join(cwd, "{0}_{1}_apercal_qa_apergest.log".format(
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
                targets, fluxcals, polcals, basedir=basedir, configfilename=configfile)
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
                targets, fluxcals, polcals, osa="", basedir=basedir)
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

    if do_apergest:
        logger.info("Running Apergest manually")
        apergest_dir = "/home/schulz/apercal/apergest/{}".format(host_name)
        os.chdir(apergest_dir)
        try:
            apergest(task_id, do_make_jsons=True, do_prepare_ingest=True,
                     do_run_ingest=True, do_delete_data=False)
        except Exception as e:
            os.chdir(cwd)
            lib.setup_logger('debug', logfile=logfile)
            logger = logging.getLogger(__name__)
            logger.warning("Running Apergest failed ({0:.3f}h)".format(
                (time.time() - start_time)/3600.))
            logger.warning(return_msg)
            logger.exception(e)
        else:
            os.chdir(cwd)
            lib.setup_logger('debug', logfile=logfile)
            logger = logging.getLogger(__name__)
            logger.info("Running Apergest ... Done ({0:.3f}h)".format(
                (time.time() - start_time)/3600.))

    # just to make sure to get back
    os.chdir(cwd)


if __name__ == "__main__":
    run_manual_processing()
