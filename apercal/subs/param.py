import os
import logging
import numpy as np

from apercal.subs import setinit as subs_setinit

logger = logging.getLogger(__name__)


def create_param_file(step):
    """
    Create a new parameter file in case there is none in the base directory as a dictionary
    """
    subs_setinit.setinitdirs(step)
    df = {}
    np.save(step.basedir + 'param.npy', df)


def add_param(step, parameter, values):
    """
    Check if the param file exists, open it, check if the parameter exists and add or overwrite the parameter.
    parameter(string): Name of the parameter in the param file
    values(diverse): The data corresponding to the parameter
    """
    subs_setinit.setinitdirs(step)
    if not os.path.isfile(step.basedir + 'param.npy'):
        create_param_file(step)
    d = np.load(step.basedir + 'param.npy').item()
    d[parameter] = values
    np.save(step.basedir + 'param.npy', d)


def del_param(step, parameter):
    """
    Delete a parameter from the parameter file.
    parameter(string): Name of the parameter to delete
    """
    subs_setinit.setinitdirs(step)
    if not os.path.isfile(step.basedir + 'param.npy'):
        logger.info('Parameter file not found! Cannot remove parameter ' + str(parameter))
    else:
        d = np.load(step.basedir + 'param.npy').item()
        try:
            del d[parameter]
            np.save(step.basedir + 'param.npy', d)
        except KeyError:
            logger.info('Parameter file does not have parameter ' + str(parameter))


def get_param(step, parameter):
    """
    Load a keyword of the parameter file into a variable
    parameter (string): Name of the keyword to load
    returns (various): The variable for the parameter
    """
    subs_setinit.setinitdirs(step)
    if not os.path.isfile(step.basedir + 'param.npy'):
        logger('Parameter file not found! Cannot load parameter ' + str(parameter))
    else:
        d = np.load(step.basedir + 'param.npy').item()
        values = d[parameter]
        return values


def get_param_def(step, parameter, default):
    """
    Load a keyword of the paramterfile into a variable, or give a default value if
    the keyword is not in the parameter file
    TODO: merge this into get_param to avoid loading param.npy too often
    step (object): step for which to do this
    parameter (string): name of the keyword to load
    parameter (object): default value
    """
    subs_setinit.setinitdirs(step)
    if not os.path.isfile(step.basedir + 'param.npy'):
        return default
    else:
        d = np.load(step.basedir + 'param.npy').item()
        if parameter in d:
            # logger.info('Parameter ' + str(parameter) + ' found in cache (param.npy).')
            return d[parameter]
    return default


def check_param(step, parameter):
    """
    Check if a list of parameters exist in the parameter file ans return True or False
    parameter (list of strings): The parameters to search for
    returns (bool): True if parameter exists, otherwise False
    """
    subs_setinit.setinitdirs(step)
    if not os.path.isfile(step.basedir + 'param.npy'):
        logger.info('Parameter file not found! Cannot load parameter ' + str(parameter))
        create_param_file(step)
    else:
        d = np.load(step.basedir + 'param.npy').item()
        if parameter in d:
            return True
    return False


def show_param(step):
    """
    Shows all the entries of the parameter file in a sorted order
    """
    subs_setinit.setinitdirs(step)
    if not os.path.isfile(step.basedir + 'param.npy'):
        logger.info('Parameter file not found!')
    else:
        d = np.load(step.basedir + 'param.npy').item()
        for k, v in d.items():
            logger.info(k, v)
