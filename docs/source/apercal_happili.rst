Running Apercal on happili
**************************

Setting up environment
======================

On happili, the following environment setup should work:

::

    source /home/apercal/pipeline/bin/activate
    source /home/apercal/atnf_miriad/miriad/MIRRC.sh
    export PATH="$PATH:/home/apercal/casa-release-4.7.0-1-el7/bin"

This will run the apercal version installed in the virtualenv /users/apercal/. This should be the most recent release. You can check this in the log, or by typing

::

    python -c 'import apercal; print(apercal.__version__); print(apercal.__file__)'

Note that you need to run python from a directory that does not contain an apercal subdirectory (so not your homedirectory), because then python will prefer to run the apercal installed there.

Running without config file
===========================

Apercal comes a default config file (default.cfg). Current practice is to copy this file and make changes to the config file. This has some problems when the layout of the config file changes. It is possible, and preferable, to always run apercal with the default config file.

To run one step of the pipeline:

::

    from apercal.modules.preflag import preflag

    p = preflag()
    p.basedir = '/data/dijkema/apertif/181211/'
    p.fluxcal = '3C295.MS'
    p.target = 'NGC807.MS'
    p.polcal = '3C138.MS'

To run all steps of the pipeline (or at least all parts that currently work), there is a convenience function start_apercal_pipeline that does this for you. Note however that the function signature may change (and we may forget to update this wiki).

::

    import apercal.pipeline

    taskid_fluxcal = 181201004
    taskid_target = 181201005
    taskid_polcal = 181201006
    beamlist_target = list(range(40))
    beamlist_fluxcal = [0]
    beamlist_polcal = [0]
    name_fluxcal = '3C295'
    name_polcal = '3C138'
    name_target = 'NGC807'
    apercal.pipeline.start_pipeline((taskid_fluxcal, name_fluxcal, beamlist_fluxcal),
                                    (taskid_polcal, name_polcal, beamlist_polcal),
                                    (taskid_target, name_target, beamlist_target))
