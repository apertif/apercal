cwlVersion: v1.0
class: Workflow

inputs:
  ms: Directory

outputs:
  msout:
    type: Directory
    outputSource: preflag/msout

steps:
  preflag:
    run: steps/preflag.cwl
    in:
      ms: ms
    out:
        [msout]
