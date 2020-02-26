AO strategies
=============

The directory ``ao_strategies`` contains the flagging strategies used by
*AOFlagger* in the *preflag* module.

Default strategy: ``target.rfis``
---------------------------------

This file contains the default flagging strategy.
It is used for the target as well as the flux and polarisation calibrator.
There have been discussions about using a different flagging strategy for
the calibrators again, but this has not been implemented.

Other (past) strategies
-----------------------

Currently, these strategies are not used.

* Flux calibrator
   * ``fluxcal_apertif_XX.rfis``
   * ``fluxcal_apertif_nopb.rfis``
   * ``fluxcal.rfis``
* Polarisation calibrator
   * ``pol_apertif_XX.rfis``
   * ``pol_apertif_nopb.rfis``
   * ``pol.rfis``
* Target
   * ``target_apertif_XX.rfis``
   * ``target_apertif_nopb.rfis``
   * ``target_conservative.rfis``

