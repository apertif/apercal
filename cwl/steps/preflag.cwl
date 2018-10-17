class: CommandLineTool
cwlVersion: v1.0
hints:
  DockerRequirement:
      dockerPull: apertif/apercal

baseCommand: [python]
inputs:
  ms:
    type: Directory

outputs:
  ms:
    type: Directory

arguments:
  - position: 0
    prefix: '-c'
    valueFrom: |
        from apercal.modules.preflag import preflag
        from os import path

        p = preflag(path.join(here, '/code/apercal/modules/default.cfg'))
        p.apercaldir = path.join(here, '/code/apercal')
        # p.input = $(inputs.ms)  # todo
        p.show(showall=True)
        p.manualflag()
        p.aoflagger_bandpass()
        preflag.aoflagger_flag()

requirements:
  - class: InlineJavascriptRequirement