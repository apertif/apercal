#!/usr/bin/env python

"""
Parse apercal.log to extract timing info per step

Usage: ./parselog.py apercal.log
"""

from __future__ import print_function

from datetime import datetime
import sys

useful_lines = []
useful_lines += ["apercal.pipeline.start_pipeline - INFO : Apercal version"]
useful_lines += ["apercal.modules.prepare"]
useful_lines += ["apercal.modules.preflag"]
useful_lines += ["apercal.modules.ccal"]
useful_lines += ["apercal.pipeline.start_pipeline - INFO : Starting crosscal QA plots"]
useful_lines += ["apercal.modules.convert"]
useful_lines += ["apercal.modules.scal"]
useful_lines += ["apercal.modules.continuum"]

original_useful_lines = list(useful_lines)

past_first = False
prev_time = None
prev_step = None

logfilename = sys.argv[1]

def parse_and_subtract(logline, prev_time, prev_step):
    """
    Print time since previous step (or nothing for the first event)

    Args:
        logline (str): log line
        prev_time (datetime or None): previous time
        prev_step (str or None): previous step name

    Returns:
        datetime: time parsed from logline
    """
    cur_time = datetime.strptime(logline.strip()[:22], "%m/%d/%Y %I:%M:%S %p")
    if prev_time:
        delta_t = cur_time - prev_time
        print(prev_step.split(" ")[0].split(".")[-1], ":".join(str(delta_t).split(":")[:2]))

    return cur_time

with open(logfilename, "r") as logfile:
    for logline in logfile:
        for pos, useful_line in enumerate(useful_lines):
            if useful_line in logline:
                cur_time = parse_and_subtract(logline, prev_time, prev_step)

                prev_time = cur_time
                prev_step = useful_line
                if past_first and useful_line == useful_lines[0]:
                    # Restart with new pipeline run
                    useful_lines = list(original_useful_lines)
                    print('---- restart', logline[:23])
                    break
                else:
                    del useful_lines[pos]

                if not past_first:
                    past_first = True
                break

    parse_and_subtract(logline, prev_time, prev_step)
