import string
import random
import datetime
import lib
import os
import time
import numpy as np
from astropy.table import Table

def get_gains(file):
    '''
    Function to create a complex python array of amplitude and phase gains from a dataset
    file (str): u,v file with the bandpass calibration
    return(array, array): an array with the amplitude and phase gains for each antenna and solution interval, a datetime array with the actual solution timesteps
    '''
    char_set = string.ascii_uppercase + string.digits  # Create a charset for random gain log file generation
    tempdir = os.path.expanduser('~') + '/apercal/temp/mirlog'
    gains_string = ''.join(random.sample(char_set * 8, 8))
    gpplt = lib.miriad('gpplt')
    gpplt.vis = file
    gpplt.log = tempdir + '/' + gains_string
    gpplt.options = 'gains'
    gpplt.yaxis = 'amp'
    cmd = gpplt.go()
    obsdate = cmd[3].split(' ')[4][0:7]
    starttime = datetime.datetime(int('20' + obsdate[0:2]), int(time.strptime(obsdate[2:5], '%b').tm_mon), int(obsdate[5:7]))
    s = Table.read(tempdir + '/' + gains_string, format='ascii')
    gpplt.yaxis = 'phase'
    gpplt.go()
    t = Table.read(tempdir + '/' + gains_string, format='ascii')
    days = np.array(t['col1'])
    times = np.array(t['col2'])
    nint = len(days)
    nant = int(len(t[0])-2)
    gain_array = np.zeros((nant, nint, 2))
    for ant in range(nant):
        gain_array[ant, :, 0] = s['col' + str(ant + 3)]
        gain_array[ant, :, 1] = t['col' + str(ant + 3)]
    time_array = [starttime + datetime.timedelta(days=int(days[step]), hours=int(times[step][0:2]), minutes=int(times[step][3:5]), seconds=int(times[step][6:8])) for step in range(nint)]
    return gain_array, time_array

def get_bp(file):
    '''
    Function to create a python array from a bandpass calibrated dataset to analyse
    file (str): u,v file with the bandpass calibration
    return(array, array): The bandpass array in the following order (antenna, frequencies, solution intervals) and a list of the frequencies
    '''
    char_set = string.ascii_uppercase + string.digits  # Create a charset for random gain log file generation
    tempdir = os.path.expanduser('~') + '/apercal/temp/mirlog'
    bp_string = ''.join(random.sample(char_set * 8, 8))
    gpplt = lib.miriad('gpplt')
    gpplt.vis = file
    gpplt.log = tempdir + '/' + bp_string
    gpplt.options = 'bandpass'
    gpplt.go()
    t = Table.read(tempdir + '/' + bp_string, format='ascii')
    freqs = np.array(np.unique(t['col1']))
    nfreq = len(freqs)
    nint = len(t['col1'])/nfreq
    nant = int(len(t[0])-1)
    bp_array = np.zeros((nant, nfreq, nint))
    for ant in range(nant):
        bp_array[ant,:,:] = np.swapaxes(t['col' + str(ant+2)].reshape(nint, nfreq),0,1)
    return bp_array, freqs

def get_delays(file):
    '''
    Function to create a numpy array with the antenna delays for each solution interval
    file (str): u,v file with the bandpass calibration
    return(array, array): an array with the delays for each antenna and solution interval in nsec, a datetime array with the actual solution timesteps
    '''
    char_set = string.ascii_uppercase + string.digits  # Create a charset for random gain log file generation
    tempdir = os.path.expanduser('~') + '/apercal/temp/mirlog'
    gains_string = ''.join(random.sample(char_set * 8, 8))
    gpplt = lib.miriad('gpplt')
    gpplt.vis = file
    gpplt.log = tempdir + '/' + gains_string
    gpplt.options = 'delays'
    cmd = gpplt.go()
    obsdate = cmd[3].split(' ')[4][0:7]
    starttime = datetime.datetime(int('20' + obsdate[0:2]), int(time.strptime(obsdate[2:5], '%b').tm_mon), int(obsdate[5:7]))
    t = Table.read(tempdir + '/' + gains_string, format='ascii')
    days = np.array(t['col1'])
    times = np.array(t['col2'])
    nint = len(days)
    nant = int(len(t[0])-2)
    delay_array = np.zeros((nant, nint))
    for ant in range(nant):
        delay_array[ant, :] = t['col' + str(ant + 3)]
    time_array = [starttime + datetime.timedelta(days=int(days[step]), hours=int(times[step][0:2]), minutes=int(times[step][3:5]), seconds=int(times[step][6:8])) for step in range(nint)]
    return delay_array, time_array
