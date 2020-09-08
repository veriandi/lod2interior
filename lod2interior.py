# Importing needed libaries
import shapefile as sf
import uuid
from lxml import etree
import pyclipper

# Created by Mirza Veriandi
# Student Number 15116068
# July 2020
# Geodesy and Geomatics Engineering Undergraduate
# Remote Sensing and Geographic Information Sciences Research Group
# Institut Teknologi Bandung (ITB)

# Reading floorplan shapefile dataset
fp_shapefile_dir = str(input('Input your floorplan shapefile data directory (example: C:/Users/.../floorplan_shapefile):\n'))
fp_sfreader = sf.Reader(fp_shapefile_dir)
fp_features = fp_sfreader.shapes()
fp_attributes = fp_sfreader.records()

# Creating a structured feature and attribute variable based on building IDs of the floorplan features
bldgIDs_All = []
for attribute in fp_attributes:
    bldgID = attribute[0]
    bldgIDs_All.append(bldgID)
bldgIDs = list(set(bldgIDs_All))

bldgsIndices = []
for bldgID in bldgIDs:
    bldgIndices = []
    for n, ID in enumerate(bldgIDs_All):
        if ID == bldgID:
            bldgIndices.append(n)
    bldgsIndices.append(bldgIndices)
    
bldgsRoomFt = []
bldgsRoomAtt = []
for i, ID in enumerate(bldgIDs):
    bldgRoomFt = []
    bldgRoomAtt = []
    for index in bldgsIndices[i]:
        bldgRoomFt.append(fp_features[index])
        bldgRoomAtt.append(fp_attributes[index])
    bldgsRoomFt.append(bldgRoomFt)
    bldgsRoomAtt.append(bldgRoomAtt)

# Defining an output variable that contains all buildings interior geometries
# Structured based on building IDs, room IDs and surface semantics
# Example: {118:{0:{'Floor':[coordinates], 'Ceiling':[Coordinates], 'InnerWall':[coordinates]}, 1:...,}, 119:...,}
roomSurfaces = {}

# Defining variables for inward offset processing of room polygons
bldgsRoomXY = []
bldgsRoomXYZ = []

# Defining a function for inward offset processing of room polygons
# The process is needed to have correct room geometries that have gap between adjacent rooms
# Wall thickness is set to 0.075 m or 7.5 cm
def InwardOffset(feature, output, thickness):
    coordinates = feature.points[:-1]
    pco = pyclipper.PyclipperOffset()
    coordsScaled = pyclipper.scale_to_clipper(coordinates)
    pco.AddPath(coordsScaled, pyclipper.JT_SQUARE, pyclipper.ET_CLOSEDPOLYGON)
    result = pco.Execute(pyclipper.scale_to_clipper(thickness))
    resultScaled = pyclipper.scale_from_clipper(result)
    
    resultScaledList = resultScaled[0]
    lastCoord = resultScaledList[0]
    
    resultScaledList.append(lastCoord)
    output.append(resultScaledList)

# Iterating inward offset process through all building features
wallThickness = float(input('Input wall thickness in meters (example: 0.075):\n'))
for bldgRoomFt in bldgsRoomFt:
    bldgRoomIOxy = []

    for roomFt in bldgRoomFt:
        InwardOffset(roomFt, bldgRoomIOxy, wallThickness)

    bldgsRoomXY.append(bldgRoomIOxy)

# Defining a function for adding Z value to inward offseted XY coordinates
# Taking the assumption that all vertex in a room base polygon having the same Z value
def addingZ(feature, coordinates, output):
    zValues = feature.z
    elevation = sum(zValues)/len(zValues)
    xyzCoordinates = []

    for coordinate in coordinates:
        xyzCoordinate = (coordinate[0], coordinate[1], elevation)
        xyzCoordinates.append(xyzCoordinate)

    output.append(xyzCoordinates)

# Iterating adding Z for all room geometries in all buildings
for i, bldgRoomXY in enumerate(bldgsRoomXY):
    bldgRoomIOxyz = []

    for n, roomCoords in enumerate(bldgRoomXY):
        addingZ(bldgsRoomFt[i][n], roomCoords, bldgRoomIOxyz)

    bldgsRoomXYZ.append(bldgRoomIOxyz)

# Defining a function for calculating storey height of a building
# Taking the assumption that in the same building, all storeys have the same height
def storeyHeight(bldgRoomFeatures, bldgRoomAttributes, floorThickness):
    storey1Elev = 0
    storey2Elev = 0
    i1 = 0
    i2 = 0

    while storey1Elev == 0:
        if bldgRoomAttributes[i1][1] == 1:
            storey1Elev = bldgRoomFeatures[i1].z[0]
        else:
            i1 += 1

    while storey2Elev == 0:
        if bldgRoomAttributes[i2][1] == 2:
            storey2Elev = bldgRoomFeatures[i2].z[0]
        else:
            i2 += 1

    height = storey2Elev - storey1Elev - floorThickness
    return(height)

# Defining a function for creating FloorSurface with the right orientation
def floor_surf(floorCoordsXYZ, floorCoordsXY, output):
    coordinates = floorCoordsXYZ
    
    if sf.signed_area(floorCoordsXY) < 0:
        coordinates.reverse()
        
    output['Floor'] = coordinates

# Defining a function for creating CeilingSurface with the right orientation
def ceiling_surf(floorCoordsXYZ, floorCoordsXY, height, output):
    coordinates = []

    for coord in floorCoordsXYZ:
        l_coord = [coord[0], coord[1], coord[2]+height]
        t_coord = tuple(l_coord)
        coordinates.append(t_coord)
    
    if sf.signed_area(floorCoordsXY) >= 0:
        coordinates.reverse()
        
    output['Ceiling'] = coordinates

# Defining a function for creating InteriorWallSurfaces for a room with the right orientation
def interiorwall_surf(floorCoordsXYZ, floorCoordsXY, height, output):
    
    interiorWallSurfaces = []

    floorCoords = []
    for coord in floorCoordsXY:
        coord_t = tuple(coord)
        floorCoords.append(coord_t)
    
    
    floorElevs = []
    for coords in floorCoordsXYZ:
        floorElevs.append(coords[2])
    floorElev = sum(floorElevs)/len(floorElevs)
    
    if sf.signed_area(floorCoordsXY) >= 0:
        floorCoords.reverse()
        
    for i in range(len(floorCoords)-1):
        coord1 = list(floorCoords[i])
        coord1.append(floorElev)
        coord2 = list(floorCoords[i+1])
        coord2.append(floorElev)
        coord3 = [coord2[0], coord2[1], floorElev+height]
        coord4 = [coord1[0], coord1[1], floorElev+height]
        surface = [tuple(coord1), tuple(coord2), tuple(coord3), tuple(coord4), tuple(coord1)]
        
        interiorWallSurfaces.append(surface)
        
    output['InteriorWall'] = interiorWallSurfaces

floorThick = float(input('Input floor thickness in meters (example: 0.4):\n'))
for i, ID in enumerate(bldgIDs):
    height = storeyHeight(bldgsRoomFt[i], bldgsRoomAtt[i], floorThick)
    roomSurfaces[ID] = {}
    roomTotal = len(bldgsRoomXYZ[i])

    for n in range(roomTotal):
        roomSurfaces[ID][n] = {}
        floorCoordsXYZ = bldgsRoomXYZ[i][n]
        floorCoordsXY = bldgsRoomXY[i][n]
        floor_surf(floorCoordsXYZ, floorCoordsXY, roomSurfaces[ID][n])
        ceiling_surf(floorCoordsXYZ, floorCoordsXY, height, roomSurfaces[ID][n])
        interiorwall_surf(floorCoordsXYZ, floorCoordsXY, height, roomSurfaces[ID][n])

# Defining CityGML namespaces
ns_base = "http://www.citygml.org/citygml/profiles/base/2.0"
ns_gen = "http://www.opengis.net/citygml/generics/2.0"
ns_core = "http://www.opengis.net/citygml/2.0"
ns_bldg = "http://www.opengis.net/citygml/building/2.0"
ns_gen = "http://www.opengis.net/citygml/generics/2.0"
ns_gml = "http://www.opengis.net/gml"
ns_xAL = "urn:oasis:names:tc:ciq:xsdschema:xAL:2.0"
ns_xlink = "http://www.w3.org/1999/xlink"
ns_xsi = "http://www.w3.org/2001/XMLSchema-instance"
ns_schemaLocation = "http://www.citygml.org/citygml/profiles/base/2.0 http://schemas.opengis.net/citygml/profiles/base/2.0/CityGML.xsd"

nsmap = {None: ns_base, 'gen': ns_gen, 'core': ns_core, 'bldg': ns_bldg, 'gen': ns_gen, 'gml': ns_gml, 'xAL': ns_xAL, 'xlink': ns_xlink, 'xsi': ns_xsi}

# Reading CityGML file and parsing the root element (CityModel) to a variable
lod2Dir = str(input('Input your building LOD2 CityGML file directory (example: C:/Users/.../Labtek9C.gml):\n'))
lod2Model = etree.parse(lod2Dir)
CityModel = lod2Model.getroot()

# Defining a function for writing surfaces to CityGML that forms a room
def writeRoom(roomGeometry, RoomElement, lod4SolidElement, CompositeSurfaceElement):
    for surfaceType in roomGeometry.keys():
        if surfaceType == 'Floor':
            surfUUID = 'UUID_' + str(uuid.uuid4()) + '_2'
            boundedBy = etree.SubElement(RoomElement, '{%s}boundedBy' % ns_bldg)
            FloorSurface = etree.SubElement(boundedBy, '{%s}FloorSurface' % ns_bldg)
            FloorSurface.set('{%s}id' % ns_gml, surfUUID)
            lod4MultiSurface = etree.SubElement(FloorSurface, '{%s}lod4MultiSurface' % ns_bldg)
            MultiSurface = etree.SubElement(lod4MultiSurface, '{%s}MultiSurface' % ns_gml)
            surfaceMember = etree.SubElement(MultiSurface, '{%s}surfaceMember' % ns_gml)
            Polygon = etree.SubElement(surfaceMember, '{%s}Polygon' % ns_gml)
            Polygon.set('{%s}id' % ns_gml, surfUUID + '_poly')
            Exterior = etree.SubElement(Polygon, '{%s}exterior' % ns_gml)
            LinearRing = etree.SubElement(Exterior, '{%s}LinearRing' % ns_gml)
            posList = etree.SubElement(LinearRing, '{%s}posList' % ns_gml, srsDimension='3')
            
            coordinates = ''
            copy = ''

            for coordinate in roomGeometry['Floor']:
                coordinates = copy + str(coordinate[0]) + ' ' + str(coordinate[1]) + ' ' + str(coordinate[2]) + ' '
                copy = coordinates

            posList.text = coordinates[:-1]
            
            slinkSurfaceMember = etree.SubElement(CompositeSurfaceElement, '{%s}surfaceMember' % ns_gml)
            OrientableSurface = etree.SubElement(slinkSurfaceMember, '{%s}OrientableSurface' % ns_gml)
            OrientableSurface.set('orientation', '-')
            baseSurface = etree.SubElement(OrientableSurface, '{%s}baseSurface' % ns_gml)
            baseSurface.set('{%s}href' % ns_xlink, '#' + surfUUID + '_poly')
            
        elif surfaceType == 'Ceiling':
            surfUUID = 'UUID_' + str(uuid.uuid4()) + '_2'
            boundedBy = etree.SubElement(RoomElement, '{%s}boundedBy' % ns_bldg)
            CeilingSurface = etree.SubElement(boundedBy, '{%s}CeilingSurface' % ns_bldg)
            CeilingSurface.set('{%s}id' % ns_gml, surfUUID)
            lod4MultiSurface = etree.SubElement(CeilingSurface, '{%s}lod4MultiSurface' % ns_bldg)
            MultiSurface = etree.SubElement(lod4MultiSurface, '{%s}MultiSurface' % ns_gml)
            surfaceMember = etree.SubElement(MultiSurface, '{%s}surfaceMember' % ns_gml)
            Polygon = etree.SubElement(surfaceMember, '{%s}Polygon' % ns_gml)
            Polygon.set('{%s}id' % ns_gml, surfUUID + '_poly')
            Exterior = etree.SubElement(Polygon, '{%s}exterior' % ns_gml)
            LinearRing = etree.SubElement(Exterior, '{%s}LinearRing' % ns_gml)
            posList = etree.SubElement(LinearRing, '{%s}posList' % ns_gml, srsDimension='3')
            
            coordinates = ''
            copy = ''

            for coordinate in roomGeometry['Ceiling']:
                coordinates = copy + str(coordinate[0]) + ' ' + str(coordinate[1]) + ' ' + str(coordinate[2]) + ' '
                copy = coordinates

            posList.text = coordinates[:-1]
            
            slinkSurfaceMember = etree.SubElement(CompositeSurfaceElement, '{%s}surfaceMember' % ns_gml)
            OrientableSurface = etree.SubElement(slinkSurfaceMember, '{%s}OrientableSurface' % ns_gml)
            OrientableSurface.set('orientation', '-')
            baseSurface = etree.SubElement(OrientableSurface, '{%s}baseSurface' % ns_gml)
            baseSurface.set('{%s}href' % ns_xlink, '#' + surfUUID + '_poly')
            
        elif surfaceType == 'InteriorWall':
            for surface in roomGeometry['InteriorWall']:
                surfUUID = 'UUID_' + str(uuid.uuid4()) + '_2'
                boundedBy = etree.SubElement(Room, '{%s}boundedBy' % ns_bldg)
                InteriorWallSurface = etree.SubElement(boundedBy, '{%s}InteriorWallSurface' % ns_bldg)
                InteriorWallSurface.set('{%s}id' % ns_gml, surfUUID)
                lod4MultiSurface = etree.SubElement(InteriorWallSurface, '{%s}lod4MultiSurface' % ns_bldg)
                MultiSurface = etree.SubElement(lod4MultiSurface, '{%s}MultiSurface' % ns_gml)
                surfaceMember = etree.SubElement(MultiSurface, '{%s}surfaceMember' % ns_gml)
                Polygon = etree.SubElement(surfaceMember, '{%s}Polygon' % ns_gml)
                Polygon.set('{%s}id' % ns_gml, surfUUID + '_poly')
                exterior = etree.SubElement(Polygon, '{%s}exterior' % ns_gml)
                LinearRing = etree.SubElement(exterior, '{%s}LinearRing' % ns_gml)
                posList = etree.SubElement(LinearRing, '{%s}posList' % ns_gml, srsDimension='3')
                
                coordinates = ''
                copy = ''
                
                for coordinate in surface:
                    coordinates = copy + str(coordinate[0]) + ' ' + str(coordinate[1]) + ' ' + str(coordinate[2]) + ' '
                    copy = coordinates
                posList.text = coordinates[:-1]
                
                slinkSurfaceMember = etree.SubElement(CompositeSurfaceElement, '{%s}surfaceMember' % ns_gml)
                OrientableSurface = etree.SubElement(slinkSurfaceMember, '{%s}OrientableSurface' % ns_gml)
                OrientableSurface.set('orientation', '-')
                baseSurface = etree.SubElement(OrientableSurface, '{%s}baseSurface' % ns_gml)
                baseSurface.set('{%s}href' % ns_xlink, '#' + surfUUID + '_poly')

# Iterate writing rooms for all buildings
for i, bldgID in enumerate(roomSurfaces.keys()):
    for CityOM in CityModel.findall('{%s}cityObjectMember' % ns_core):
        for building in CityOM:
            interiorRoom = etree.SubElement(building, '{%s}interiorRoom' % ns_bldg)
            if building.attrib['{%s}id' % ns_gml][3:] == str(bldgID):
                for n, roomID in enumerate(roomSurfaces[bldgID].keys()):
                    roomAttributes = bldgsRoomAtt[i][n]
                    Room = etree.SubElement(interiorRoom, '{%s}Room' % ns_bldg)
                    
                    # Adding storey attribute
                    Storey = etree.SubElement(Room, '{%s}stringAttribute' % ns_gen)
                    Storey.set('name', 'Storey')
                    StoreyVal = etree.SubElement(Storey, '{%s}value' % ns_gen)
                    StoreyVal.text = str(roomAttributes[1])
                    
                    # Adding room number attribute
                    RoomNumber = etree.SubElement(Room, '{%s}stringAttribute' % ns_gen)
                    RoomNumber.set('name', 'RoomNumber')
                    RoomNumberVal = etree.SubElement(RoomNumber, '{%s}value' % ns_gen)
                    RoomNumberVal.text = str(roomAttributes[2])
                    
                    # Adding room name attribute
                    RoomName = etree.SubElement(Room, '{%s}stringAttribute' % ns_gen)
                    RoomName.set('name', 'RoomName')
                    RoomNameVal = etree.SubElement(RoomName, '{%s}value' % ns_gen)
                    RoomNameVal.text = roomAttributes[3]

                    lod4Solid = etree.SubElement(Room, '{%s}lod4Solid' % ns_bldg)
                    Solid = etree.SubElement(lod4Solid, '{%s}Solid' % ns_gml)
                    exterior = etree.SubElement(Solid, '{%s}exterior' % ns_gml)
                    CompositeSurface = etree.SubElement(exterior, '{%s}CompositeSurface' % ns_gml)
                    writeRoom(roomSurfaces[bldgID][roomID], Room, lod4Solid, CompositeSurface)

# Writing the enriched CityGML file
et = etree.ElementTree(CityModel)
outputDir = str(input('Input output directory (example: C:/Users/.../LOD2Interior.gml):\n'))
et.write(outputDir, xml_declaration=True, encoding='utf-8', pretty_print= True)