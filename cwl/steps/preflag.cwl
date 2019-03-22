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
      - entry: $(inputs.ms)
        writable: true


baseCommand: [python]

inputs:
  ms:
    type: Directory


outputs:
  preflagged:
    type: Directory
    outputBinding:
      glob: $(inputs.ms.basename)


arguments:
  - prefix: '-c'
    valueFrom: |
      import logging
      logging.basicConfig(level=logging.DEBUG)
      from apercal.modules.preflag import preflag
      from os import getcwd

      p = preflag()
      p.target = "$(inputs.ms.path)"
      p.fluxcal = ""
      p.polcal = ""
      p.subdirification = False
      p.go()
