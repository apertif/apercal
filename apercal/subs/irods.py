import subprocess
import os

from getdata_alta import get_alta_dir

FNULL = open(os.devnull, 'w')


def getstatus_alta(date, task_id, beam):
    """
    Funtion to check if the data is on ALTA.
    date (int or str): Date of the observing weekend of the data. Usually the first day of the weekend (Friday).
    Format: YYMMDD
    task_id (int or str): ID number of the observation. Format: NNN
    beam (int or str): Beam number to copy. Format: NN
    return (bool): True if the file is available, False if not
    """
    altadir = get_alta_dir(date, int(task_id), int(beam), False)
    cmd = "ils {}".format(altadir)
    retcode = subprocess.call(cmd.split(), stdout=FNULL, stderr=FNULL)
    return retcode == 0
