import datetime
import os
import random
import string
import time

import numpy as np
from astropy.table import Table

from apercal import subs
from apercal.libs import lib


def get_nants(file_):
    """
    Funtion to get the number of antennas from a MIRIAD gain file
    file_ (str): the log file with the table
    returns (int): Number of antennas
    """
    with open(file_, 'rw') as gaintxt:
        gainlines = gaintxt.readlines()
        nants = int(gainlines[3].split(' ')[-1])
    gaintxt.close()
    return nants


def get_nbins(file_):
    """
    Funtion to get the number of frequency bins in a MIRIAD gain file
    file_ (str): the log file with the table
    returns (int): Number of frequency bins
    """
    for i, line in enumerate(open(file_).readlines()):
        if 'Frequency bin:' in line:
            nline = i
    with open(file_, 'rw') as gaintxt:
        gainlines = gaintxt.readlines()
        nbins = int(gainlines[nline].split(' ')[-1].rstrip('\n'))
    gaintxt.close()
    return nbins


def get_nsols(file_):
    """
    Funtion to get the number of solution intervals from a MIRIAD gain file
    file_ (str): the log file with the table
    returns (int): Number of solution intervals
    """
    for i, line in enumerate(open(file_).readlines()):
        if 'Frequency bin:' in line:
            nline = i
        else:
            lastline = i
    nlines = lastline - nline
    nants = get_nants(file_)
    if nants > 6:
        nsols = nlines/2
    else:
        nsols = nlines
    return nsols


def get_ndims(file_):
    """
    Wrapper funtion to get the dimension of the selfcal gain file
    file_ (str): u,v file with the gain calibration
    returns (int, int, int): Number of antennas, number of frequency bins, number of time intervals
    """
    char_set = string.ascii_uppercase + string.digits  # Create a charset for random gain log file generation
    tempdir = subs.managetmp.manage_tempdir('mirlog')
    subs.managetmp.clean_tempdir('mirlog')
    gains_string = ''.join(random.sample(char_set * 8, 8))
    gpplt = lib.miriad('gpplt')
    gpplt.vis = file_
    gpplt.log = tempdir + '/' + gains_string
    gpplt.yaxis = 'amp'
    cmd = gpplt.go()
    nants = get_nants(tempdir + '/' + gains_string)
    nbins = get_nbins(tempdir + '/' + gains_string)
    nsols = get_nsols(tempdir + '/' + gains_string)
    return nants, nbins, nsols


def reformat_table(file_):
    """
    Function to change the file format of a MIRIAD ggplt table to an ascii table compatible one
    file_ (str): the log file with the table
    """
    nants = get_nants(file_)
    if nants > 6:
        os.system('sed /^#.*/d ' + file_ + ' > ' + file_ + '_tmp')
        with open(file_ + '_tmp', 'r') as f:
            content = f.readlines()
            with open(file_ + '_refor', 'w') as g:
                for i in xrange(1, len(content) + 1):
                    if i % 2 == 0:
                        g.write(content[i - 2].strip() + '   ' + content[i - 1].strip() + '\n')
                g.close()
            f.close()
        os.system('mv ' + file_ + '_refor ' + file_)


def get_amps(file_):
    """
    Function to create a python array of selfcal amplitude gains from a dataset
    file_ (str): u,v file with the gain calibration
    return(array, array): an array with the phase gains for each antenna, frequency bin and solution interval, a
                          datetime array with the actual solution timesteps
    """
    char_set = string.ascii_uppercase + string.digits  # Create a charset for random gain log file generation
    tempdir = subs.managetmp.manage_tempdir('mirlog')
    subs.managetmp.clean_tempdir('mirlog')
    gains_string = ''.join(random.sample(char_set * 8, 8))
    gpplt = lib.miriad('gpplt')
    gpplt.vis = file_
    gpplt.log = tempdir + '/' + gains_string
    gpplt.yaxis = 'amp'
    cmd = gpplt.go()
    nants = get_nants(tempdir + '/' + gains_string)
    nbins = get_nbins(tempdir + '/' + gains_string)
    nsols = get_nsols(tempdir + '/' + gains_string)
    reformat_table(tempdir + '/' + gains_string)
    obsdate = cmd[3].split(' ')[4][0:7]
    starttime = datetime.datetime(int('20' + obsdate[0:2]), int(time.strptime(obsdate[2:5], '%b').tm_mon),
                                  int(obsdate[5:7]))
    s = Table.read(tempdir + '/' + gains_string, format='ascii')
    days = np.array(s['col1'][0:nsols])
    times = np.array(s['col2'][0:nsols])
    time_array = [starttime + datetime.timedelta(days=int(days[step]), hours=int(times[step][0:2]), minutes=int(times[step][3:5]),
                                       seconds=int(times[step][6:8])) for step in range(nsols)]
    gain_array = np.zeros([nants, nbins, nsols])
    for ant in range(nants):
        gain_array[ant, :, :] = np.reshape(s['col' + str(ant + 3)][nsols:], (1, nbins, nsols))
    return gain_array, time_array


def get_phases(file_):
    """
    Function to create a python array of selfcal phase gains from a dataset
    file_ (str): u,v file with the gain calibration
    return(array, array): an array with the phase gains for each antenna, frequency bin and solution interval, a
                          datetime array with the actual solution timesteps
    """
    char_set = string.ascii_uppercase + string.digits  # Create a charset for random gain log file generation
    tempdir = subs.managetmp.manage_tempdir('mirlog')
    subs.managetmp.clean_tempdir('mirlog')
    gains_string = ''.join(random.sample(char_set * 8, 8))
    gpplt = lib.miriad('gpplt')
    gpplt.vis = file_
    gpplt.log = tempdir + '/' + gains_string
    gpplt.yaxis = 'phase'
    cmd = gpplt.go()
    nants = get_nants(tempdir + '/' + gains_string)
    nbins = get_nbins(tempdir + '/' + gains_string)
    nsols = get_nsols(tempdir + '/' + gains_string)
    reformat_table(tempdir + '/' + gains_string)
    obsdate = cmd[3].split(' ')[4][0:7]
    starttime = datetime.datetime(int('20' + obsdate[0:2]), int(time.strptime(obsdate[2:5], '%b').tm_mon),
                                  int(obsdate[5:7]))
    s = Table.read(tempdir + '/' + gains_string, format='ascii')
    days = np.array(s['col1'][0:nsols])
    times = np.array(s['col2'][0:nsols])
    time_array = [starttime + datetime.timedelta(days=int(days[step]), hours=int(times[step][0:2]), minutes=int(times[step][3:5]),
                                       seconds=int(times[step][6:8])) for step in range(nsols)]
    gain_array = np.zeros([nants, nbins, nsols])
    for ant in range(nants):
        gain_array[ant, :, :] = np.reshape(np.unwrap(s['col' + str(ant + 3)][nsols:], discont=90), (1, nbins, nsols))
    return gain_array, time_array


def get_bp(file_):
    """
    Function to create a python array from a bandpass calibrated dataset to analyse
    file_ (str): u,v file with the bandpass calibration
    return(array, array): The bandpass array in the following order (antenna, frequencies, solution intervals) and a
                          list of the frequencies
    """
    char_set = string.ascii_uppercase + string.digits  # Create a charset for random gain log file generation
    tempdir = subs.managetmp.manage_tempdir('mirlog')
    # tempdir = os.path.expanduser('~') + '/apercal/temp/mirlog'
    bp_string = ''.join(random.sample(char_set * 8, 8))
    gpplt = lib.miriad('gpplt')
    gpplt.vis = file_
    gpplt.log = tempdir + '/' + bp_string
    gpplt.options = 'bandpass'
    gpplt.go()
    reformat_table(tempdir + '/' + bp_string)
    t = Table.read(tempdir + '/' + bp_string, format='ascii')
    freqs = np.array(np.unique(t['col1']))
    nfreq = len(freqs)
    nint = len(t['col1']) / nfreq
    nant = int(len(t[0]) - 1)
    bp_array = np.zeros((nant, nfreq, nint))
    for ant in range(nant):
        bp_array[ant, :, :] = np.swapaxes(t['col' + str(ant + 2)].reshape(nint, nfreq), 0, 1)
    return bp_array, freqs


def get_delays(file_):
    """
    Function to create a numpy array with the antenna delays for each solution interval
    file_ (str): u,v file with the bandpass calibration
    return(array, array): an array with the delays for each antenna and solution interval in nsec, a datetime array
                          with the actual solution timesteps
    """
    char_set = string.ascii_uppercase + string.digits  # Create a charset for random gain log file_ generation
    tempdir = subs.managetmp.manage_tempdir('mirlog')
    # tempdir = os.path.expanduser('~') + '/apercal/temp/mirlog'
    gains_string = ''.join(random.sample(char_set * 8, 8))
    gpplt = lib.miriad('gpplt')
    gpplt.vis = file_
    gpplt.log = tempdir + '/' + gains_string
    gpplt.options = 'delays'
    cmd = gpplt.go()
    reformat_table(tempdir + '/' + gains_string)
    obsdate = cmd[3].split(' ')[4][0:7]
    starttime = datetime.datetime(int('20' + obsdate[0:2]), int(time.strptime(obsdate[2:5], '%b').tm_mon),
                                  int(obsdate[5:7]))
    t = Table.read(tempdir + '/' + gains_string, format='ascii')
    days = np.array(t['col1'])
    times = np.array(t['col2'])
    nint = len(days)
    nant = int(len(t[0]) - 2)
    delay_array = np.zeros((nant, nint))
    for ant in range(nant):
        delay_array[ant, :] = t['col' + str(ant + 3)]
    time_array = [
        starttime + datetime.timedelta(days=int(days[step]), hours=int(times[step][0:2]), minutes=int(times[step][3:5]),
                                       seconds=int(times[step][6:8])) for step in range(nint)]
    return delay_array, time_array
