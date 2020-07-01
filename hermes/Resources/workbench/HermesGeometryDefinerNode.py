# FreeCAD Part module
# (c) 2001 Juergen Riegel
#
# Part design module

#***************************************************************************
#*   (c) Juergen Riegel (juergen.riegel@web.de) 2002                       *
#*                                                                         *
#*   This file is part of the FreeCAD CAx development system.              *
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU Lesser General Public License (LGPL)    *
#*   as published by the Free Software Foundation; either version 2 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   FreeCAD is distributed in the hope that it will be useful,            *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU Library General Public License for more details.                  *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with FreeCAD; if not, write to the Free Software        *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         *
#*   Juergen Riegel 2002                                                   *
#***************************************************************************/

# import FreeCAD modules
import FreeCAD,FreeCADGui, WebGui
import HermesTools
from HermesTools import addObjectProperty

from PyQt5 import QtGui,QtCore

if FreeCAD.GuiUp:
    import FreeCADGui
    from PySide import QtCore

import json

import copy

import HermesNode
import CfdFaceSelectWidget
import HermesPart



# -----------------------------------------------------------------------#
# This enables us to open a dialog on the left with a click of a button #
# -----------------------------------------------------------------------#

# *****************************************************************************
# -----------**************************************************----------------
#                          #CGEDialogPanel start
# -----------**************************************************----------------
# *****************************************************************************

# Path To bc UI
ResourceDir = FreeCAD.getResourceDir() if list(FreeCAD.getResourceDir())[-1] == '/' else FreeCAD.getResourceDir() + "/"
path_to_ge_ui = ResourceDir + "Mod/Hermes/Resources/ui/bcdialog.ui"


class CGEDialogPanel:

    def __init__(self, obj):
        # Create widget from ui file
        self.form = FreeCADGui.PySideUic.loadUi(path_to_ge_ui)

        # Connect Widgets' Buttons
        # self.form.m_pOpenB.clicked.connect(self.browseJsonFile)

        #        self.GEObjName=obj.Name

        # Face list selection panel - modifies obj.References passed to it
        self.faceSelector = CfdFaceSelectWidget.CfdFaceSelectWidget(self.form.m_pFaceSelectWidget,
                                                                    obj, True, False)

    def addGE(self, geType):
        # add  geType to options at GE dialog
        self.form.m_pBCTypeCB.addItem(geType)

    def setCurrentGE(self, GEName):
        # update the current value in the comboBox
        self.form.m_pBCTypeCB.setCurrentText(GEName)

    def setCallingObject(self, callingObjName):
        # get obj Name, so in def 'accept' can call the obj
        self.callingObjName = callingObjName

    def readOnlytype(self):
        # update the 'type' list to 'read only' - unChangeable
        self.form.m_pBCTypeCB.setEnabled(0)

    def accept(self):
        # Happen when Close Dialog
        # get the current GE type name from Dialog
        GEtype = self.form.m_pBCTypeCB.currentText()


        # calling the nodeObj from name
        callingObject = FreeCAD.ActiveDocument.getObject(self.callingObjName)

        # calling the function that create the new GE Object
        callingObject.Proxy.geDialogClosed(callingObject, GEtype)

        # close the Dialog in FreeCAD
        FreeCADGui.Control.closeDialog()
        self.faceSelector.closing()

    def reject(self):
        self.faceSelector.closing()
        return True


#
# *****************************************************************************
# -----------**************************************************----------------
#                                   # GE module start
# -----------**************************************************----------------
# *****************************************************************************

def makeGENode(name, TypeList, GENodeData, Nodeobj):
    """ Create a Hermes Geometry Entity object """

    #    # Object with option to have children
    #    obj = FreeCAD.ActiveDocument.addObject("App::DocumentObjectGroupPython", name)

    # Object can not have children
    obj = FreeCAD.ActiveDocument.addObject("App::FeaturePython", name)


    # add GENodeobj(obj) as child of Nodeobj
    Nodeobj.addObject(obj)

    # initialize propeties and so at the new GE obj
    _HermesGE(obj, TypeList, GENodeData)

    if FreeCAD.GuiUp:
        _ViewProviderGE(obj.ViewObject)
    return obj

# ======================================================================
class _CommandHermesGeNodeSelection:
    """ CFD physics selection command definition """

    def GetResources(self):
        ResourceDir = FreeCAD.getResourceDir() if list(FreeCAD.getResourceDir())[-1] == '/' else FreeCAD.getResourceDir() + "/"
        icon_path = ResourceDir + "Mod/Hermes/Resources/icons/GENode.png"
        return {'Pixmap': icon_path,
                'MenuText': QtCore.QT_TRANSLATE_NOOP("Hermes_GE_Node", "Hermes Geometry Entities Node"),
                'ToolTip': QtCore.QT_TRANSLATE_NOOP("Hermes_GE_Node", "Creates new Hermes Geometry Entities Node")}

    def IsActive(self):
        return HermesTools.getActiveHermes() is not None

    def Activated(self):
        FreeCAD.ActiveDocument.openTransaction("Choose appropriate Geometry Entities Node")
        isPresent = False
        members = HermesTools.getActiveHermes().Group
        for i in members:
            if isinstance(i.Proxy, _CfdPhysicsModel):
                FreeCADGui.activeDocument().setEdit(i.Name)
                isPresent = True

        # Allow to re-create if deleted
        if not isPresent:
            FreeCADGui.doCommand("")
            FreeCADGui.addModule("HermesGeNode")
            FreeCADGui.addModule("HermesTools")
            FreeCADGui.doCommand(
                "HermesTools.getActiveHermes().addObject(HermesGeNode.makeGENode())")
            FreeCADGui.ActiveDocument.setEdit(FreeCAD.ActiveDocument.ActiveObject.Name)


if FreeCAD.GuiUp:
    FreeCADGui.addCommand('Hermes_GeNode', _CommandHermesGeNodeSelection())

# ======================================================================


# =============================================================================
# Hermes GE class
# =============================================================================
class _HermesGE:
    """ The Hermes GE (Geometry Entity) """

    def __init__(self, obj, TypeList, GENodeData):

        obj.Proxy = self

        self.TypeList = TypeList
        self.GENodeData = GENodeData
        self.initProperties(obj)

    def initProperties(self, obj):

        # ^^^ Constant properties ^^^

        # References property - keeping the faces and part data attached to the GE obj
        addObjectProperty(obj, 'References', [], "App::PropertyPythonObject", "", "Boundary faces")

        # link property - link to other object (beside parent)
        addObjectProperty(obj, "OtherParents", None, "App::PropertyLinkGlobal", "Links", "Link to")

        # Active property- keep if obj has been activated (douuble clicked get active)
        addObjectProperty(obj, "IsActiveGE", False, "App::PropertyBool", "", "Active heraccept object in document")

        # GENodeDataString property - keep the json GE node data as a string
        addObjectProperty(obj, "GENodeDataString", "-1", "App::PropertyString", "GENodeData", "Data of the node", 4)

        # Type property - list of all GE types
        addObjectProperty(obj, "Type", self.TypeList, "App::PropertyEnumeration", "GE Type",
                          "Type of Boundry Condition")
        obj.setEditorMode("Type", 1)  # Make read-only (2 = hidden)

        # Update Values at the properties from GENodeData
        obj.Type = self.GENodeData["Type"]
        obj.Label = self.GENodeData["Name"]  # automatically created with object.
        obj.GENodeDataString = json.dumps(self.GENodeData)  # convert from json to string

        #  ^^^^^ Properties from Json  ^^^

        # get GE node List of properties from 'nodeData'
        ListProperties = self.GENodeData["Properties"]

        # Create each property from the list
        for x in ListProperties:
            # get property'num' object ; num =1,2,3 ...
            propertyNum = ListProperties[x]

            # get needed parameters to create a property
            prop = propertyNum["prop"]
            init_val = propertyNum["init_val"]
            Type = propertyNum["type"]
            Heading = propertyNum["Heading"]
            tooltip = propertyNum["tooltip"]

            # add Object's Property
            addObjectProperty(obj, prop, init_val, Type, Heading, tooltip)

    def UpdateFacesInJson(self, obj):

        # get workflowObj
        Nodeobj = obj.getParentGroup()
        workflowObj = Nodeobj.getParentGroup()

        # get Export path from workflowObj
        dirPath = workflowObj.ExportJSONFile

        # Create basic structure of a part object
        Part_strc = {
            "Name": "",
            "Path": "",
            "faces": []
        }

        # create list the will contain all part Objects
        # add tmp part obj to ListPartObj
        ListPartObj = []
        workflowObj.Proxy.partList = {}

        # Loop all the References in the object
        for Ref in obj.References:
            # example Refernces structure : obj.References=[('Cube','Face1'),('Cube','Face2')]
            # example Ref structure :Ref=('Cube','Face1')

            # get Name and face from Corrent Reference
            PartName = Ref[0]  # givenPartName
            PartFace = Ref[1]  # face

            # Loop all ListPartObj -
            nPartIndex = -1
            nIndex = 0
            for PartObj in ListPartObj:
                # check if Object exist in list
                if PartName == PartObj['Name']:
                    # save part index in list
                    nPartIndex = nIndex
                    break
                nIndex = nIndex + 1

            # if Part not exists in ListPartObj -
            # create a new part obj and add it to the ListPartObj
            if (nPartIndex == -1):


                # update Part_strc Name
                Part_strc['Name'] = PartName

                # update Part_strc Path
                Part_strc['Path'] = dirPath + '/'

                # update Part_strc face list
                Part_strc['faces'] = [PartFace]

                # add part obj to ListPartObj
                mydata = copy.deepcopy(Part_strc)
                ListPartObj.append(mydata)

                # update the part dictionary(faces/vertices) in the list
                # use here the label and not the name
                if FreeCAD.ActiveDocument.getObject(PartName) is not None:
                    partLabel = FreeCAD.ActiveDocument.getObject(PartName).Label
                    workflowObj.Proxy.partList[partLabel] = HermesPart.HermesPart(PartName).getpartDict()

            # update face list of the part
            else:
                # add the face to part's face list
                ListPartObj[nPartIndex]['faces'].append(PartFace)

        # Create basic structure of a facelist (string) in the length of ListPartObj
        # structure example:
        # -- "faceList":{
        # --     "Part1":{ },
        # --     "Part2":{ },
        # --     "Part3":{ }
        # --  }

        x = 1
        faceListStr = "{"
        for PartObj in ListPartObj:
            if (x > 1):
                faceListStr += ','
            partStr = '"Part' + str(x) + '":{}'
            faceListStr += partStr
            x = x + 1
        faceListStr += "}"

        # create Hermesworkflow obj to allow caliing def "ExportPart"
        Nodeobj = obj.getParentGroup()
        workflowObj = Nodeobj.getParentGroup()

        # convert structure from string to json
        faceList = json.loads(faceListStr)

        # loop all part objects in ListPartObj
        for y in range(len(ListPartObj)):
            # get PartObj from the ListPartObj
            PartObj = ListPartObj[y]

            # Create Part'Node' ; Node =1,2,3 ...
            PartNode = 'Part' + str(y + 1)

            # update the PartObj data at the current PartNode in faceList
            faceList[PartNode] = PartObj

            workflowObj.Proxy.ExportPart(obj, str(PartObj['Name']))

        # Update faceList attach to the GE at the GEnodeData
        self.GENodeData["faceList"] = faceList

        # update Label in Json
        self.GENodeData["Name"] = obj.Label

        # Update GEnodeData  at the GENodeDataString by converting from json to string
        self.GENodeDataString = json.dumps(self.GENodeData)
        return

    def initFacesFromJson(self, obj):

        # get faceList attach to the GE from GEnodeData
        faceList = self.GENodeData["faceList"]

        # create Hermesworkflow obj to allow caliing def "loadPart"
        Nodeobj = obj.getParentGroup()
        workflowObj = Nodeobj.getParentGroup()

        for x in faceList:
            # get the partnum  from facelist (in case more then 1 part attach to the GE)
            # property'num' ; num =1,2,3 ...
            partnum = faceList[x]

            # get Name and path of the part , and list of faces attach to the part
            PartName = partnum["Name"]
            PartPath = partnum["Path"]
            PartFaces = partnum["faces"]

            # Create full path of the part for Import
            pathPartStr = PartPath + PartName + ".stp"

            # Call 'loadPart' from 'hermesWorkflow' to load part
            givenPartName = workflowObj.Proxy.loadPart(workflowObj, pathPartStr)

            # ToDo: Check if this line is needed
            if len(givenPartName) == 0:
                continue

            # update the Reference(faces) list attach to the the GEObj -
            for face in PartFaces:
                tmp = (givenPartName, face)  # Reference structure
                obj.References.append(tmp)

        return

    def setCurrentPropertyGE(self, obj, ListProperties):
        # update the current value of all properties' GE object
        for x in ListProperties:
            # get property'num' object ; num =1,2,3 ...
            propertyNum = ListProperties[x]

            # get the prop parameter
            prop = propertyNum["prop"]

            # get the prop current_val
            current_val = propertyNum["current_val"]

            # get the current_val at the prop
            setattr(obj, prop, current_val)

    def onDocumentRestored(self, obj):
        # when restored- initilaize properties
        self.initProperties(obj)

        if FreeCAD.GuiUp:
            _ViewProviderGE(obj.ViewObject)

    def doubleClickedGENode(self, obj):

        # create CGEDialogPanel Object
        geDialog = CGEDialogPanel(obj)

        # get NodeObj to get nodeData
        NodeObj = obj.getParentGroup()

        # get GE type list from nodeDate - *in case not 'readonly'* have list of GEtypes
        GETypes = NodeObj.Proxy.nodeData["GeometryFaceTypes"]
        TypeList = GETypes["TypeList"]

        # add the GE types to options at GE dialog
        for types in TypeList:
            geDialog.addGE(types)

        # update the first value to be showen in the comboBox
        geDialog.setCurrentGE(obj.Type)

        # set read only GE type
        geDialog.readOnlytype()

        # add node Object name to the geDialog name - used when "accept"
        geDialog.setCallingObject(obj.Name)

        # show the Dialog in FreeCAD
        FreeCADGui.Control.showDialog(geDialog)

        return

    def geDialogClosed(self, callingObject, GEtype):
        # todo: is needed?
        pass

    def UpdateGENodePropertiesData(self, obj):
        # update the properties in the "GEnodeData"
        # use this func before exporting Json

        # get node List of properties
        ListProperties = self.GENodeData["Properties"]

        for y in ListProperties:

            # get property'num' object ; num =1,2,3 ...
            propertyNum = ListProperties[y]

            # get the prop parameter
            prop = propertyNum["prop"]

            # get the Object Property current value from property object
            current_val = getattr(obj, prop)

            # update the value at the propertyNum[prop]
            if type(current_val) is not int and type(current_val) is not float and type(current_val) is not list:
                # In case of 'Quantity property' (velocity,length etc.), 'current_val' need to be export as a string
                propertyNum["current_val"] = str(current_val)

            else:
                propertyNum["current_val"] = current_val

            # update propertyNum in ListProperties
            ListProperties[y] = propertyNum

        # update ListProperties in nodeData
        self.GENodeData["Properties"] = ListProperties

        # Update GEnodeData  at the GENodeDataString by converting from json to string
        obj.GENodeDataString = json.dumps(self.GENodeData)

        return


# =============================================================================
#      "_ViewProviderNode" class
# =============================================================================
class _ViewProviderGE:
    """ A View Provider for the Hermes GE Node container object. """

    # =============================================================================
    #     General interface for all visual stuff in FreeCAD This class is used to
    #     generate and handle all around visualizing and presenting GE objects from
    #     the FreeCAD App layer to the user.
    # =============================================================================

    def __init__(self, vobj):
        vobj.Proxy = self
        self.GENodeType = vobj.Object.Type

    def getIcon(self):
        ResourceDir = FreeCAD.getResourceDir() if list(FreeCAD.getResourceDir())[-1] == '/' else FreeCAD.getResourceDir() + "/"
        icon_path = ResourceDir + "Mod/Hermes/Resources/icons/GENode.png"

        return icon_path

    def attach(self, vobj):
        self.ViewObject = vobj
        self.bubbles = None

    def updateData(self, obj, prop):
        # We get here when the object of GE Node changes
        return

    def onChanged(self, obj, prop):
        return

    def doubleClicked(self, vobj):
        vobj.Object.Proxy.doubleClickedGENode(vobj.Object)
        return

    def __getstate__(self):
        return

    def __setstate__(self, state):
        return None

# *****************************************************************************
# -----------**************************************************----------------
#                                   #GE module end
# -----------**************************************************----------------
# *****************************************************************************
#