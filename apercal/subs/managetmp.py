import os


def manage_tempdir(subdir):
    """
    Creates a temporary directory if it does not exist and cleans one if it exists
    subdir(string): Name of the temporary subdirectory in /apercal/temp/
    returns (string): absolute path of temporary directory
    """
    create_tempdir(subdir)
    tempdir = clean_tempdir(subdir)
    return tempdir


def create_tempdir(subdir):
    """
    Function to check if a temporary directoy exists and create one if not
    subdir(string): Name of the temporary subdirectory in /apercal/temp/
    returns (string): absolute path of temporary directory
    """
    tempdir = os.path.expanduser('~') + '/apercal/temp/' + str(subdir)
    if not os.path.exists(tempdir):
        os.system('mkdir -p ' + tempdir)
    return tempdir


def clean_tempdir(subdir):
    """
    Function to clean the temporary directory from any temporary files
    subdir(string): Name of the temporary subdirectory in /apercal/temp/
    returns (string): absolute path of temporary directory
    """
    tempdir = os.path.expanduser('~') + '/apercal/temp/' + str(subdir)
    os.system('rm -rf ' + tempdir + '/*')
    return tempdir
