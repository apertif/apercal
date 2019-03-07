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
  target_preflagged:
    type: Directory
    outputBinding:
      glob: $(inputs.target.basename)

  polcal_preflagged:
    type: Directory
    outputBinding:
      glob: $(inputs.polcal.basename)

  fluxcal_preflagged:
    type: Directory
    outputBinding:
      glob: $(inputs.fluxcal.basename)


# other potential interesting outputs:
#
# 3C138-flags-00-11.png
# 3C138-flags-02-07.png
# 3C138-flags-04-05.png
# 3C295-flags-00-11.png
# 3C295-flags-02-07.png
# 3C295-flags-04-05.png
# 3C295_Bpass.txt
# NGC807-flags-00-11.png
# NGC807-flags-02-07.png
# NGC807-flags-04-05.png


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
