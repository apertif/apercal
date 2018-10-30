import numpy as np


def calc_synbeam(beamnumbers, sbeams):
    """
    Calculates the mimimum major and minor axis as well as the pa of a synthesised beam giving multiple input beams
    beamnumbers (list): Beam numbers referring to the beam parameters
    sbeams (numpy array): The input minor, major and pa parameters of the beams
    returns (numpy array, list of strings): The major and minor axis and pa of the beam to convolve to, list of the
                          rejected chunks
    """
    bmaj_rej = reject_outliers(sbeams[:, 0], 20.0)
    bmin_rej = reject_outliers(sbeams[:, 1], 20.0)
    bpa_rej = reject_outliers(sbeams[:, 2], 20.0)
    rejlist = list(set(list(bmaj_rej[0]) + list(bmin_rej[0]) + list(bpa_rej[0])))
    brej = [beamnumbers[i] for i in rejlist]
    bmaj_filt = np.delete(sbeams[:, 0], rejlist)
    bmin_filt = np.delete(sbeams[:, 1], rejlist)
    bpa_filt = np.delete(sbeams[:, 2], rejlist)
    bmaj = np.nanmax(bmaj_filt) * 1.02
    bmin = np.nanmax(bmin_filt) * 1.02
    bpa = np.nanmedian(bpa_filt)
    bpar = np.array([bmaj, bmin, bpa])
    return sorted(brej, reverse=True), bpar


def reject_outliers(data, m):
    """
    Algorithm to remove outliers by median
    data (numpy array): Data to detect outliers in
    m (float): Outlier threshold
    returns (numpy array): Data without outliers
    """
    d = np.abs(data - np.nanmedian(data))
    mdev = np.nanmedian(d)
    s = d / (mdev if mdev else 1.0)
    return np.where(data[s >= m])
