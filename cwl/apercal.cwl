cwlVersion: v1.0
class: Workflow

inputs:
  target: Directory
  fluxcal: Directory
  polcal: Directory

outputs:
  calibrated:
    type: Directory
    outputSource: convert/target_converted

steps:
  preflag:
    run: steps/preflag.cwl
    in:
      target: target
      fluxcal: fluxcal
      polcal: polcal
    out:
      - target_preflagged
      - fluxcal_preflagged
      - polcal_preflagged

  convert:
    run: steps/convert.cwl
    in:
      target: preflag/target_preflagged
      fluxcal: preflag/fluxcal_preflagged
      polcal: preflag/polcal_preflagged
    out:
      - target_converted
      - fluxcal_converted
      - polcal_converted


# convert
# ccal
# scal
# line
# transfer
# continuum
# mosaic
