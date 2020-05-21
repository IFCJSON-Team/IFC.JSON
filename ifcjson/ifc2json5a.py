# IFCJSON_python - ifc2json5a.py
# Convert IFC SPF file to IFC.JSON-4
# https://github.com/IFCJSON-Team

# MIT License

# Copyright (c) 2020 Jan Brouwer <jan@brewsky.nl>

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import uuid
import subprocess
import ifcopenshell
import ifcopenshell.guid as guid
import ifcjson.common as common

class IFC2JSON5a:
    def __init__(self, ifcFilePath):
        self.ifcFilePath = ifcFilePath
        self.ifcModel = ifcopenshell.open(ifcFilePath)

        # Dictionary referencing all objects with a GlobalId that are already created
        self.id_objects = {}

        # Representations are kept seperate to be added to the end of the list
        self.representations = {}

    def spf2Json(self):
        objData = self.getObjData(self.ifcFilePath)
        jsonObjects= []
        entityIter = iter(self.ifcModel)
        for entity in entityIter:
            self.entityToDict(entity, objData)
        for key in self.id_objects:
            jsonObjects.append(self.id_objects[key])
        for key in self.representations:
            jsonObjects.append(self.representations[key])
        return jsonObjects

    def entityToDict(self, entity, objData):
        ref = {
            'type': entity.is_a()
        }
        attr_dict = entity.__dict__

        # check for globalid
        if 'GlobalId' in attr_dict:
            uuid = guid.split(guid.expand(attr_dict["GlobalId"]))[1:-1]
            ref['ref'] = uuid
            if not attr_dict['GlobalId'] in self.id_objects:
                d = {
                    'type': entity.is_a()
                }

                for i in range(0,len(entity)):
                    attr = entity.attribute_name(i)
                    attrKey = common.toLowerCamelcase(attr)
                    if attr == "GlobalId":
                        d[attrKey] = uuid
                    else:
                        if attr in attr_dict:

                            # Skip all IFC entities that are not part of IFC.JSON5a
                            if type(attr_dict[attr]) == ifcopenshell.entity_instance:

                                # Skip IfcOwnerHistory
                                if attr_dict[attr].is_a() == 'IfcOwnerHistory':
                                    continue

                                # Skip IfcGeometricRepresentationContext
                                if attr_dict[attr].is_a() == 'IfcGeometricRepresentationContext':
                                    continue

                            # Use representation from OBJ list if present
                            if attr == 'Representation':
                                if objData:
                                    if attr_dict['GlobalId'] in objData:
                                        id = guid.split(guid.expand(guid.new()))[1:-1]
                                        d['representations'] = [
                                            {
                                                "class": "ShapeRepresentation",
                                                "ref": id
                                            }
                                        ]
                                        self.representations[id] = {
                                            "class": "ShapeRepresentation",
                                            "globalId": id,
                                            "representationIdentifier": "Body",
                                            "representationType": "OBJ",
                                            "items": [
                                                objData[attr_dict['GlobalId']]
                                            ]
                                        }
                                        continue
                                    else:
                                        continue


                            # Skip ObjectPlacement: all OBJ geometries are in world coordinates
                            if attr == 'ObjectPlacement':
                                continue

                            jsonValue = self.getEntityValue(attr_dict[attr], objData)
                            if jsonValue:
                                d[attrKey] = jsonValue
                            if attr_dict[attr] == None:
                                continue
                            elif isinstance(attr_dict[attr], ifcopenshell.entity_instance):
                                d[attrKey] = self.entityToDict(attr_dict[attr], objData)
                            elif isinstance(attr_dict[attr], tuple):
                                subEnts = []
                                for subEntity in attr_dict[attr]:
                                    if isinstance(subEntity, ifcopenshell.entity_instance):
                                        subEntJson = self.entityToDict(subEntity, objData)
                                        if subEntJson:
                                            subEnts.append(subEntJson)
                                    else:
                                        subEnts.append(subEntity)
                                if len(subEnts) > 0:
                                    d[attrKey] = subEnts
                            else:
                                d[attrKey] = attr_dict[attr]
                self.id_objects[attr_dict['GlobalId']] = d
            return ref
        else:
            d = {
                'type': entity.is_a()
            }

            for i in range(0,len(entity)):
                attr = entity.attribute_name(i)
                attrKey = common.toLowerCamelcase(attr)
                if attr in attr_dict:
                    if not attr == 'OwnerHistory':
                        jsonValue = self.getEntityValue(attr_dict[attr], objData)
                        if jsonValue:
                            d[attrKey] = jsonValue
                        if attr_dict[attr] == None:
                            continue
                        elif isinstance(attr_dict[attr], ifcopenshell.entity_instance):
                            d[attrKey] = self.entityToDict(attr_dict[attr], objData)
                        elif isinstance(attr_dict[attr], tuple):
                            subEnts = []
                            for subEntity in attr_dict[attr]:
                                if isinstance(subEntity, ifcopenshell.entity_instance):
                                    subEntJson = self.entityToDict(subEntity, objData)
                                    if subEntJson:
                                        subEnts.append(subEntJson)
                                else:
                                    subEnts.append(subEntity)
                            if len(subEnts) > 0:
                                d[attrKey] = subEnts
                        else:
                            d[attrKey] = attr_dict[attr]
            return d

    def getEntityValue(self, value, objData):
        if value == None:
            jsonValue = None
        elif isinstance(value, ifcopenshell.entity_instance):
            jsonValue = self.entityToDict(value, objData)
        elif isinstance(value, tuple):
            jsonValue = None
            subEnts = []
            for subEntity in value:
                subEnts.append(self.getEntityValue(subEntity, objData))
            jsonValue = subEnts
        else:
            jsonValue = value
        return jsonValue

    # convert IFC SPF file into OBJ using IfcConvert and extract OBJ objects
    def getObjData(self, ifcFilePath):
        objFilePath = os.path.splitext(ifcFilePath)[0] + '.obj'

        # Convert IFC to OBJ using IfcConvert (could also be done for glTF or Collada)
        # subprocess.run([
        #     './ifcopenshell/IfcConvert',
        #     ifcFilePath,
        #     objFilePath,
        #     '--use-element-guids'
        # ])
        if os.path.isfile(objFilePath):
            objData = {}
            header = True
            groupId = ''
            groupData = []
            f = open(objFilePath, 'r')
            for line in f:

                # find group
                if line[0] == 'g':
                    header = False
                    objData[groupId] = '\n'.join(groupData)
                    groupId = line.split()[1]
                    groupData = []
                else:
                    if header:
                        pass
                    else:
                        groupData.append(line)
            return objData
        else:
            print('Creating intermediate OBJ failed')
            return None