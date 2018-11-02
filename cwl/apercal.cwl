cwlVersion: v1.0
class: Workflow

inputs:
  target: Directory
  fluxcal: Directory
  polcal: Directory

outputs:
  calibrated:
    type: Directory
    outputSource: preflag/preflagged

steps:
  preflag:
    run: steps/preflag.cwl
    in:
      target: target
      fluxcal: fluxcal
      polcal: polcal
    out:
        [preflagged]
