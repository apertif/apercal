import os
import numpy as np

import subs.setinit

def create_param_file(self):
    '''
    Create a new paramater file in case there is none in the base directory as a dictionary
    '''
    subs.setinit.setinitdirs(self)
    df = {}
    np.save(self.basedir + 'param.npy', df)

def add_param(self, parameter, values):
    '''
    Check if the param file exists, open it, check if the parameter exists and add or overwrite the parameter.
    parameter(string): Name of the parameter in the param file
    values(diverse): The data corresponding to the parameter
    '''
    subs.setinit.setinitdirs(self)
    if os.path.isfile(self.basedir + 'param.npy') != True:
        create_param_file(self)
    d = np.load(self.basedir + 'param.npy').item()
    d[parameter] = values
    np.save(self.basedir + 'param.npy', d)

def del_param(self, parameter):
    '''
    Delete a parameter from the parameter file.
    parameter(string): Name of the parameter to delete
    '''
    subs.setinit.setinitdirs(self)
    if os.path.isfile(self.basedir + 'param.npy') != True:
        print('# Parameter file not found! Cannot remove parameter ' + str(parameter) + ' #')
    else:
        d = np.load(self.basedir + 'param.npy').item()
        try:
            del d[parameter]
            np.save(self.basedir + 'param.npy', d)
        except KeyError:
            print('# Parameter file does not have parameter '+ str(parameter) + ' #')

def get_param(self, parameter):
    '''
    Load a keyword of the parameter file into a variable
    parameter (string): Name of the keyword to load
    returns (various): The variable for the parameter
    '''
    subs.setinit.setinitdirs(self)
    if os.path.isfile(self.basedir + 'param.npy') != True:
        print('# Parameter file not found! Cannot load parameter ' + str(parameter) + ' #')
    else:
        d = np.load(self.basedir + 'param.npy').item()
        values = d[parameter]
    return values

def check_param(self, parameter):
    '''
    Check if a list of paramaters exist in the parmaater file ans return True or False
    parameter (list of strings): The parameters to search for
    returns (bool): True if parameter exists, otherwise False
    '''
    subs.setinit.setinitdirs(self)
    if os.path.isfile(self.basedir + 'param.npy') != True:
        print('# Parameter file not found! Cannot load parameter ' + str(parameter) + ' #')
    else:
        d = np.load(self.basedir + 'param.npy').item()
        if parameter in d:
            status = True
        else:
            status = False
    return status

def show_param(self):
    '''
    Shows all the entries of the parameter file in a sorted order
    '''
    subs.setinit.setinitdirs(self)
    if os.path.isfile(self.basedir + 'param.npy') != True:
        print('# Parameter file not found! #')
    else:
        d = np.load(self.basedir + 'param.npy').item()
        for k, v in d.items():
            print(k, v)