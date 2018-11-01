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
  msout:
    type: Directory
    outputBinding:
      glob: $(inputs.ms.path)

arguments:
  - prefix: '-c'
    valueFrom: |
        from apercal.modules.preflag import preflag
        from os import getcwd

        p = preflag()
        p.target = "$( inputs.ms.basename )"
        p.basedir = getcwd() + '/'
        p.show(showall=True)
        p.go()
