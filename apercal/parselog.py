#!/usr/bin/env python

"""
Parse apercal.log to extract timing info per step

Usage: ./parselog.py apercal.log
"""

from __future__ import print_function

from datetime import datetime
import sys


def parse_time(logline):
    """
    Extract time from log line, returns None if it doesn't start with a time.
    Ignores pymp lines

    Args:
        logline (str): log line, starting with a time (or not)

    Returns:
        datetime: Time of the log line, or None if it didn't start with one
     """
    try:
        logtime = datetime.strptime(logline.strip()[:22], "%m/%d/%Y %I:%M:%S %p")
    except ValueError:
        logtime = None

    return logtime

def parse_and_subtract(logline, prev_time, prev_step):
    """
    Print time since previous step (or nothing for the first event)

    Args:
        logline (str): log line
        prev_time (datetime or None): previous time
        prev_step (str or None): previous step name

    Returns:
        tuple[datetime, msg]: time parsed from logline, step name, duration
    """
    cur_time = parse_time(logline)
    stepname = None
    duration = None
    if prev_time:
        delta_t = cur_time - prev_time
        stepname, duration = prev_step.split(" ")[0].split(".")[-1], ":".join(str(delta_t).split(":")[:2])

    return cur_time, stepname, duration


def parselog(logfilename):
    """
    Parse an apercal log and extract timing info

    Params:
         logfilename (str): Name of logfile
    Returns:
         List[Tuple[str, str]]: list of stepname, duration (both strings)
    """
    useful_lines = []
    useful_lines += ["apercal.pipeline.start_pipeline - INFO : Apercal version"]
    useful_lines += ["apercal.modules.prepare"]
    useful_lines += ["apercal.modules.preflag"]
    useful_lines += ["apercal.modules.ccal"]
    useful_lines += ["apercal.pipeline.start_pipeline - INFO : Starting crosscal QA plots"]
    useful_lines += ["apercal.modules.convert"]
    useful_lines += ["apercal.modules.scal"]
    useful_lines += ["apercal.modules.continuum"]
    useful_lines += ["apercal.modules.line"]
    useful_lines += ["dataqa.crosscal"]

    original_useful_lines = list(useful_lines)

    past_first = False
    prev_time = None
    prev_step = None

    result = []
    with open(logfilename, "r") as logfile:
        for logline in logfile:
            for pos, useful_line in enumerate(useful_lines):
                this_time = parse_time(logline)
                if this_time:
                    last_time = this_time
                if useful_line in logline:
                    prev_time, stepname, duration = parse_and_subtract(logline, prev_time, prev_step)
                    if stepname:
                        result += [(stepname, duration)]
                    prev_step = useful_line
                    if past_first and useful_line == useful_lines[0]:
                        # Restart with new pipeline run
                        useful_lines = list(original_useful_lines)
                        # print('---- restart', logline[:23])
                        result = []
                        break
                    else:
                        del useful_lines[pos]

                    if not past_first:
                        past_first = True
                    break

        delta_t = last_time - prev_time
        result += [(prev_step.split(" ")[0].split(".")[-1], ":".join(str(delta_t).split(":")[:2]))]

    return result

if __name__ == '__main__':
    result = parselog(sys.argv[1])
    for (stepname, timing) in result:
        print(stepname, timing)
