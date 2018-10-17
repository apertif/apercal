cwlVersion: v1.0
class: Workflow

requirements:
  ScatterFeatureRequirement: {}

inputs:
  targets: Directory[]
  fluxcal: Directory
  polcal: Directory

outputs:
  calibrated_targets: Directory[]

steps:
  preflag:
    run: steps/preflag.cwl
    in:
      targets: targets
      fluxcal: fluxcal
      polcal: polcal
    out:
        [calibrated_targets]