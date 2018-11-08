$namespaces:
  cwltool: http://commonwl.org/cwltool#

class: CommandLineTool

cwlVersion: v1.0

hints:
  DockerRequirement:
      dockerPull: apertif/apercal

  cwltool:InplaceUpdateRequirement:
    inplaceUpdate: true

requirements:
  InitialWorkDirRequirement:
      listing:
      - entry: $(inputs.target)
        writable: true
      - entry: $(inputs.fluxcal)
        writable: true
      - entry: $(inputs.polcal)
        writable: true

baseCommand: [python]

inputs:
  target:
    type: Directory

  polcal:
    type: Directory

  fluxcal:
    type: Directory

outputs:
  preflagged:
    type: Directory
    outputBinding:
      glob: $(inputs.target.basename)

arguments:
  - prefix: '-c'
    valueFrom: |
        import logging
        logging.basicConfig(level=logging.INFO)
        from apercal.modules.preflag import preflag
        from os import getcwd

        p = preflag()
        p.target = "$(inputs.target.path)"
        p.fluxcal = "$(inputs.fluxcal.path)"
        p.polcal = "$(inputs.polcal.path)"
        p.subdirification = False
        p.go()
