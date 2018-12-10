import casacore.tables as pt
import numpy as np


def has_good_modeldata(vis):
    """Test whether a model column exists and is not only 1 or 0

    Args:
        vis (string): input MS file

    Returns:
        bool: True if 'good' model data exists
    """
    t = pt.table(vis)

    if "MODEL_DATA" not in t.colnames():
        # Bad data: no model column
        return False

    vis_max = pt.taql("SELECT gmax(abs(MODEL_DATA)) as res from $t").getcol("res")[0]
    vis_min = pt.taql("SELECT gmin(abs(MODEL_DATA)) as res from $t").getcol("res")[0]

    if np.isclose(vis_min, 0.) and np.isclose(vis_max, 1.):
        # Bad data: only default values
        return False
    else:
        # Actual good model data
        return True


def has_correcteddata(vis):
    """
    Test if a corrected_data column exists
    vis(string): input MS file
    return(bool): True if corrected_data column exists, otherwise False
    """
    t = pt.table(vis)

    if "CORRECTED_DATA" not in t.colnames():
        # Bad data: no corrected_data column
        return False
    else:
        return True


def add_caltables(ct, interp, addct, addinterp):
    """
    Funtion to autimatically handle the adding of on-the-fly calibration table expressions in the CASA syntax

    ct (string): Calibration table string
    interp (string): Interpolation string
    addct (string): Calibration table string to add
    addinterp (string): Interpolation string to add

    returns(string, string): The updated calibration table string, the updated inteprolation string
    """
    if ct == '""' and interp == '""':
        newct = addct
        newinterp = addinterp
    else:
        newct = ct + ',' + addct
        newinterp = interp + ',' + addinterp
    return newct, newinterp


def get_source_name(msname):
    """
    Get the source name from a Measurement Set

    Args:
        msname (str): full path to a Measurement Set

    Returns:
        str: Source name (e.g. 3C295)
    """
    query = "SELECT NAME FROM {}/FIELD".format(msname)
    res_table = pt.taql(query)
    return res_table[0]["NAME"]


def get_nchan(msname):
    """
    Get the number of channels from a Measurement Set

    Args:
        msname (str): full path to a Measurement Set

    Returns:
        int: number of channels (in first spectral window)
    """
    assert(isinstance(msname,str))
    spectralwindowtable = pt.table(msname + '::SPECTRAL_WINDOW', ack=False)
    nchan = spectralwindowtable.getcol("CHAN_FREQ").shape[1]
    return nchan
