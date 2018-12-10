import numpy as np
import casacore.tables as pt
from apercal.subs import misc
from apercal.subs.msutils import get_nchan

np.set_printoptions(threshold=np.nan)


def create_bandpass(dataset, bp_file):
    bandpass = np.array(
        [0.70227, 0.73712, 0.80926, 0.89405, 0.96263, 1.00208, 1.00529, 0.98781, 0.9634, 0.93708, 0.92206, 0.92462,
         0.93452, 0.95439, 0.96635, 0.97066, 0.95942, 0.95291, 0.94206, 0.93929, 0.939, 0.94255, 0.95318, 0.95749,
         0.96032, 0.95377, 0.95048, 0.94293, 0.94176, 0.94381, 0.95029, 0.95584, 0.95239, 0.95433, 0.95168, 0.94484,
         0.94459, 0.94238, 0.94807, 0.95948, 0.96151, 0.95937, 0.95313, 0.94635, 0.93813, 0.9386, 0.94353, 0.95085,
         0.96222, 0.96702, 0.96331, 0.95387, 0.93449, 0.92417, 0.92177, 0.93646, 0.95761, 0.98863, 1.00578, 0.99527,
         0.95907, 0.89373, 0.81069, 0.73628])
    # Get the number of channels of the dataset
    nchannels = get_nchan(dataset)
    channels = range(nchannels)
    ants = np.array(misc.create_antnames())
    nants = len(ants)
    feeds = np.array(misc.create_feednames())
    nfeeds = len(feeds)
    nbandpass = len(bandpass)
    niterbandpass = (nchannels / nbandpass)
    # Create the single arrays with all the numbers
    antarray = np.repeat(ants, nchannels * nfeeds)
    feedarray = np.tile(np.repeat(feeds, nchannels), nants)
    chanarray = (np.tile(channels, nfeeds * nants)).astype('S5')
    valuearray = (np.tile(bandpass, niterbandpass * nfeeds * nants)).astype('S6')
    # Combine the different arrays
    concatarray = np.stack((antarray, feedarray, chanarray, valuearray), axis=1)
    # Save the array to file
    np.savetxt(bp_file, concatarray, fmt='%s %s %s %s', delimiter='\t')
