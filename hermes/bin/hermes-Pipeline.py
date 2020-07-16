import argparse
from hermes import expandPipeline
from hermes import hermesWorkflow
import json
import os
import pathlib

parser = argparse.ArgumentParser()
parser.add_argument('command', nargs=1, type=str)
parser.add_argument('args', nargs='*', type=str)

args = parser.parse_args()

exapnder = expandPipeline()

def expand_handler(arguments):

    templatePath = arguments[0]
    newTemplatePath = arguments[1]
    parametersPath = arguments[2] if len(arguments) > 2 else None

    newTemplate = exapnder.expand(pipelinePath=templatePath,parametersPath=parametersPath)
    with open(newTemplatePath, 'w') as fp:
        json.dump(newTemplate, fp)

def buildPython_handler(arguments):

    templatePath = arguments[0]
    pythonPath = arguments[1]
    WDPath = arguments[2] if len(arguments) > 2 else str(pathlib.Path(pythonPath).parent.absolute())
    builder = arguments[3] if len(arguments) > 3 else "luigi"

    flow = hermesWorkflow(templatePath, WDPath,"")
    build = flow.build(builder)
    with open(pythonPath, "w") as file:
        file.write(build)

def executeLuigi_handler(arguments):

    pythonPath = arguments[0]
    cwd = pathlib.Path().absolute()
    moduleParent = pathlib.Path(pythonPath).parent.absolute()
    os.chdir(moduleParent)
    os.system(f"python3 -m luigi --module {os.path.basename(pythonPath)} finalnode_xx_0 --local-scheduler")
    os.chdir(cwd)

globals()['%s_handler' % args.command[0]](args.args)