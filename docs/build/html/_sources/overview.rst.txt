Overview of Apercal pipeline
============================

Introduction
------------

This brief overview of the Apercal pipeline is based on the Apercal specification document (APERCal.pdf) in combination with the pipeline itself. The goal is to give a generic (but somewhat specific) insight into the various modules within Apercal and what they are doing. More specific/detailed documentation to come elsewhere.

Each module can be run individually though some modules depend on the data products created by others.

0. Pipeline
-----------

The pipeline runs all modules listed below except for *Mosaic*. Most steps process 5 to 10 beams in parallel which is optimized for running on happili. The only exception is the *Prepare* module which is run sequentially and the *Line* module which is already parallelized for creating the cubes of a single beam. 

1. Prepare
----------

* Goal: Download data from ALTA and sort into folders
* Input: Requested target + calibrator observation task IDs
* Output: ``*.MS`` data products, in directory structure

Check if observation directories exist; if not, create them.
Check if observation data products exist; if not, download them.

2. Preflag
----------

* Goal: Apply known flags and conduct automatic flagging
* Input: ``*.MS`` data products, in directory structure
* Output: ``*.MS`` data products (changed in place)

Flag data where antennas are shadowed (preflag.shadow)
Flag subband edges, specifically channels 0-1 and 63-64 (preflag.edges)
Flag ghost channels, specifically channels 16 and 48 (preflag.ghosts)
Apply manual flags (preflag.manual), which can be any of:

Autocorrelations (preflag.manualflag_auto)
Named antennas, e.g. 'RT2,RTD'? (preflag.manualflag_antenna)
Correlations, e.g. 'XY,YX,YY' (preflag.manualflag_corr)
Baselines, e.g. 'ant1&ant2'? (preflag.manualflag_baseline)
Channels, e.g. '0~5;120~128' (preflag.manualflag_channel)
Time, e.g. '09:14:0~09:54:0' (preflag.manualflag_time)

Apply AOflagger strategy to data-set (preflag.aoflagger):

Create bandpass solution and apply to data (preflag.aoflagger_bandpass)
AOflagging on data-set (preflag.aoflagger_flag)

3. Crosscal
-----------

* Goal: Calibrate the data using calibrator observation.
* Input: Flagged MS for calibrators, Flagged MS for target.
* Output: Calibrated MS (changed in place), caltables (``*.Df``, ``*.Kcross``, ``*.Xf``, ``*.Bscan``, ``*.G0ph``, ``*.G1ap``, ``*.K``)

Create TEC correction images/calibration tables (ccal.TEC)
Carry out bandpass calibration (ccal.bandpass)
Calculate amplitude and phase gains using fluxcal (ccal.gains)
Calculate global delay calibrations using fluxcal (ccal.global_delay)
Calculate crosshand delays using polcal (ccal.crosshand_delay)
Get leakage corrections using fluxcal (ccal.leakage)
Calculate polarisation angle corrections using polcal (ccal.polarisation_angle)
Apply correction tables to calibrators (ccal.transfer_to_cal)
Apply correction tables to target beams (ccal.transfer_to_target)

4. Convert
-------------

* Goal: Convert between CASA/Miriad/UVFITS/other formats.
* Input: Calibrated MS
* Output: ``*.UVFITS`` / ``*.mir`` files

The default configuration will remove the UVFITS file

5. Selfcal
----------

* Goal: Self-calibrate the visibilities.
* Input: Converted Mir files
* Output: ``*.mir``/``*_amp.mir`` files

6. Continuum
------------

* Goal: Deconvolve and clean the data to produce continuum images.
  Create a multifrequncy image and images based on frequency chunks
* Input: Converted Mir file and selfcal Mir files
* Output: ``*.fits``

7. Line
-------

* Goal: Split the full bandwidth into frequency chunks with small overlap and produce continuum-subtracted line emission cubes for each frequency chunks
* Input: Converted Mir file and selfcal Mir files
* Output: ``*.fits``

8. Polarisation
---------------

* Goal: Generate Stokes Q,U,V continuum images.
* Input: Converted Mir file and selfcal Mir files
* Output: ``*.fits``

9. Mosaic
---------

* Goal: Mosaic data from different beams into one large field. This step is not done automatically
* Input: Continuum image fits files
* Output: ``*.fits``

10. Transfer
------------

* Goal: Create self-calibrated visibility data which can be transferred to ALTA
* Input: Converted Mir file and selfcal Mir files
* Output: ``*.UVFITS``

