import json

import maya.cmds as cmds
import maya.mel as mel

from ngSkinTools2.api import log
from ngSkinTools2.api.python_compatibility import Object


class NamedPaintTarget(Object):
    MASK = "mask"
    DUAL_QUATERNION = "dq"


class MirrorDirection(Object):
    DIRECTION_NEGATIVETOPOSITIVE = 0
    DIRECTION_POSITIVETONEGATIVE = 1
    DIRECTION_GUESS = 2
    DIRECTION_FLIP = 3


class MllInterface(Object):
    """

    A wrapper object to call functionality from ngst2Layers command.
    Most operations operate on current selection, or on target mesh that
    was set in advance. All edit operations are undoable.

    Example usage:

    .. code-block:: python

        from ngSkinTools.mllInterface import MllInterface

        mll = MllInterface()
        mll.setCurrentMesh('myMesh')

        mll.initLayers()
        id = mll.createLayer('initial weights')
        mll.setInfluenceWeights(id,0,[0.0,0.0,1.0,1.0])

        ...

    """

    TARGET_REFERENCE_MESH = 'ngSkinTools#TargetRefMesh'

    def __init__(self, mesh=None):
        self.log = log.getLogger("MllInterface")
        self.setCurrentMesh(mesh)

    def setCurrentMesh(self, mesh):
        """
        Set mesh we'll be working on with in this wrapper. Use None to operate on current selection instead.

        :param str mesh: mesh node name/path
        """
        self.mesh = mesh

    def initLayers(self):
        """
        initializes layer data node setup for target mesh
        """
        self.ngSkinLayerCmd(lda=True)

    def getLayersAvailable(self):
        """
        returns true if layer data is available for target mesh

        :rtype: bool
        """
        try:
            result = self.ngSkinLayerCmd(q=True, lda=True)
            return result
        except Exception as err:
            return False

    def getCurrentLayer(self):
        """
        get layer that is marked as selected on MLL side; current layer is used for many things, for example, as a paint target.

        :rtype: int
        """
        result = self.ngSkinLayerCmd(q=True, cl=True)
        if result == 0:
            return None
        return result

    def getTargetInfo(self):
        """
        Returns skin cluster node name where skinLayer data
        is (or can be) attached for current selection

        If current selection is not suitable for attaching layers,
        returns None

        :rtype: str
        """
        return self.ngSkinLayerCmd(q=True, ldt=True)

    def getVertCount(self):
        """
        For initialized layer info, returns number of vertices layer manager sees in the mesh.
        This might be different to actual vertex count in the mesh, if mesh has post-skin cluster mesh
        modifiers (as vertex merge or smooth)

        :rtype: int
        """
        return self.ngSkinLayerCmd(q=True, vertexCount=True)

    def getLayerName(self, layerId):
        """
        get layer name by ID

        :param int layerId: layer ID
        :rtype: str

        """
        return self.ngSkinLayerCmdMel("-id {0} -q -name".format(int(layerId)))

    def setLayerName(self, layerId, name):
        """
        set layer name by ID
        """
        self.ngSkinLayerCmd(e=True, id=int(layerId), name=name)

    def getLayerOpacity(self, layerId):
        """
        Returns layer opacity as float between ``0.0`` and ``1.0``
        """
        return float(self.ngSkinLayerCmdMel('-id {0} -q -opacity'.format(int(layerId))))

    def setLayerOpacity(self, layerId, opacity):
        """
        Set opacity for given layer. Use values between ``0.0`` and ``1.0``
        """
        self.ngSkinLayerCmd(e=True, id=int(layerId), opacity=opacity)

    def isLayerEnabled(self, layerId):
        """
        Returns ``True``, if layer on/off flag is turned on
        """
        return bool(self.ngSkinLayerCmdMel('-id {0} -q -enabled'.format(int(layerId))))

    def setLayerEnabled(self, layerId, enabled):
        """
        Turn layer on/off. Use ``True`` / ``False`` for 'enabled' value.
        """
        self.ngSkinLayerCmd(e=True, id=int(layerId), enabled=enabled)

    def listLayers(self):
        """
        returns iterator to layer list
        """
        layersData = self.ngSkinLayerCmd(q=True, listLayers=True)
        return json.loads(layersData)

    def __asTypeList(self, _type, result):
        if result is None:
            return []

        return [_type[i] for i in result]

    def __asFloatList(self, result):
        return self.__asTypeList(float, result)

    def __asIntList(self, result):
        return self.__asTypeList(int, result)

    def __floatListAsString(self, floatList):
        """
        returns empty string for None and []
        otherwise, returns a list of floats, comma delimited
        """
        if not floatList:
            return ""

        def formatFloat(value):
            return str(value)

        return ",".join([formatFloat(i) for i in floatList])

    def __intListAsString(self, values):
        return ",".join([str(i) for i in values])

    def setLayerParent(self, layerId, parentLayerId):
        if parentLayerId is None:
            parentLayerId = 0
        self.ngSkinLayerCmd(e=True, id=int(layerId), parent=int(parentLayerId))

    def getLayerParent(self, layerId):
        result = self.ngSkinLayerCmdMel('-id {0} -q -parent'.format(layerId))
        if result == 0:
            return None
        return result

    def getLayerMask(self, layerId):
        """
        returns layer mask weights as float list. if mask is not initialized, returns empty list
        """
        return self.getInfluenceWeights(layerId, NamedPaintTarget.MASK)

    def setLayerMask(self, layerId, weights):
        """
        Set mask for given layer. Supply float list for weights, e.g. ``[0.0,1.0,0.6]``.
        Supply empty list to set mask into uninitialized state.
        """
        self.setInfluenceWeights(layerId, NamedPaintTarget.MASK, weights)

    def hasDqBlendTarget(self, layerId):
        return self.ngSkinLayerCmdMel('-id {0} -paintTarget "{1}" -q -hasPaintTarget '.format(layerId, NamedPaintTarget.DUAL_QUATERNION)) != 0

    def getDualQuaternionWeights(self, layerId):
        """
        returns layer DQ weights as float list. if DQ weights are not painted for this layer, returns empty list
        """
        return self.getInfluenceWeights(layerId, NamedPaintTarget.DUAL_QUATERNION)

    def setDualQuaternionWeights(self, layerId, weights):
        """
        Set dual-quaternion weights for given layer. Supply float list for weights, e.g. ``[0.0,1.0,0.6]``.
        Supply empty list to set into uninitialized state.
        """
        self.setInfluenceWeights(layerId, NamedPaintTarget.DUAL_QUATERNION, weights)

    def getInfluenceWeights(self, layerId, influence):
        """
        returns influence weights as float list.
        :param influence: either a logical influence index or named influences "mask", "dq"
        """
        return self.__asFloatList(self.ngSkinLayerCmdMel('-id {0} -paintTarget {1} -q -w '.format(layerId, influence)))

    def setInfluenceWeights(self, layerId, influence, weights, undoEnabled=True):
        """
        Set weights for given influence in a layer. Provide weights as float list; vertex count should match result of :py:meth:`~.getVertCount`
        If weight values are higher than 1.0, they will be capped at 1.0.
        """
        self.ngSkinLayerCmd(e=True, id=int(layerId), paintTarget=influence, vertexWeights=self.__floatListAsString(weights), undoEnabled=undoEnabled)

    def snapshotLayerWeights(self, layerId):
        """
        remembers current weights and restores them after undo; redo restores weights that were there before first undo
        """
        self.ngSkinLayerCmd(e=True, id=int(layerId), createWeightsSnapshot=True)

    def setLayerWeightsBufferSize(self, layerId, numInfluences):
        """
        sets layer weights buffer size no less than X influences
        """
        self.ngSkinLayerCmd(e=True, id=int(layerId), wbs=numInfluences)

    def ngSkinLayerCmd(self, *args, **kwargs):
        # import inspect
        # import sys
        # sys.__stderr__.write("\n".join(["stack: {1} ({2} in {3})".format(*i) for i in inspect.stack()])+"\n")

        if self.mesh is not None:
            if self.mesh == self.TARGET_REFERENCE_MESH:
                kwargs['targetReferenceMesh'] = True
            else:
                args = (self.mesh,) + args
        # self.log.info("ngst2Layers %r %r",args,kwargs)
        return cmds.ngst2Layers(*args, **kwargs)

    def ngSkinLayerCmdMel(self, melCmd):
        melCmd = "ngst2Layers " + melCmd
        if self.mesh is not None:
            if self.mesh == MllInterface.TARGET_REFERENCE_MESH:
                melCmd += " -targetReferenceMesh"
            else:
                melCmd += " " + self.mesh

        # self.log.info(melCmd)

        return mel.eval(melCmd)

    def createLayer(self, name, forceEmpty=False):
        """
        creates new layer with given name and returns it's ID; when forceEmpty flag is set to true,
        layer weights will not be populated from skin cluster.

        :return: layer ID
        :rtype: int
        """
        return self.ngSkinLayerCmd(name=name, add=True, forceEmpty=forceEmpty)

    def deleteLayer(self, layerId):
        """
        Deletes given layer in target mesh
        """
        self.ngSkinLayerCmd(rm=True, id=int(layerId))

    def setCurrentLayer(self, layerId):
        """
        Set current layer
        :param int layerId: layerId earlier obtained via createLayer; can be None, will equate to having to current layer
        """
        if layerId is None:
            layerId = 0
        return self.ngSkinLayerCmd(cl=int(layerId))

    def setCurrentPaintTarget(self, paintTarget):
        """
        universal way to set current paint target.

        :param paintTarget: influence index or named paint target: ``mask``, ``dq``;
        """
        self.ngSkinLayerCmd(pt=paintTarget)

    def getCurrentPaintTarget(self):
        """
        if there is a named target selected, returns "mask" or "dq";
        if no target is selected, returns ``None``;
        otherwise returns influence index
        """
        return self.ngSkinLayerCmd(q=True, pt=True)

    def getPaintTargetPath(self):
        return self.ngSkinLayerCmd(q=True, paintTargetPath=True)

    def getMirrorAxis(self):
        """
        Get axis that is used in the mirror operation. Can be one of: 'x', 'y', 'z', or 'undefined'
        """
        result = self.ngSkinLayerCmd(q=True, mirrorAxis=True)
        if result == 'undefined':
            return None
        return result

    def mirrorLayerWeights(
        self,
        layerId,
        mirrorWidth=0.0,
        mirrorLayerWeights=True,
        mirrorLayerMask=True,
        mirrorDualQuaternion=True,
        mirrorDirection=MirrorDirection.DIRECTION_POSITIVETONEGATIVE,
    ):
        """
        Mirror weights in a layer.

        :param int layerId: id of a target layer
        :param float mirrorWidth: width of a seam axis
        :param bool mirrorLayerMask: should mask be mirrored?
        :param bool mirrorLayerWeights: should weights be mirrored?
        :param bool mirrorDualQuaternion: should dual quaternion blend weights be mirrored?
        :param int mirrorDirection: direction to mirror; use MirrorDirection constants for reference.
        """

        self.ngSkinLayerCmd(
            id=layerId,
            mirrorWidth=mirrorWidth,
            mirrorLayerWeights=mirrorLayerWeights,
            mirrorLayerMask=mirrorLayerMask,
            mirrorLayerDq=mirrorDualQuaternion,
            mirrorDirection=mirrorDirection,
        )

    def configureInfluencesMirrorMapping(self, influencesMapping):
        """
        :param dict influencesMapping: a "source->destination"
        """

        self.ngSkinLayerCmd(configureMirrorMapping=True, influencesMapping=self.influencesMapToList(influencesMapping))

    def beginDataUpdate(self):
        """
        starts batch data update mode, putting layer data into suspended state - certain
        internal updates are switched off, making multiple layer data changes like setLayerWeights
        or setLayerOpacity run faster; updates will take place when endDataUpdate is called.

        begin..endDataUpdate() pairs can be stacked (e.g. methods inside begin..end can call begin..end
        themselves) - updates will resume only when most outer pair finishes executing.
        """
        self.ngSkinLayerCmd(beginDataUpdate=True)

    def endDataUpdate(self):
        """
        end batch update.
        """
        self.ngSkinLayerCmd(endDataUpdate=True)

    def batchUpdateContext(self):
        """
        a helper method to use in a "with" statement, e.g.:

        .. code-block:: python

            with mll.batchUpdateContext():
                mll.setLayerWeights(...)
                mll.setLayerOpacity(...)

        this is the same as:

        .. code-block:: python

            mll.beginDataUpdate()
            try:
                mll.setLayerWeights(...)
                mll.setLayerOpacity(...)
            finally:
                mll.endDataUpdate()
        """

        return BatchUpdateContext(self)

    def setWeightsReferenceMesh(self, vertices, triangles):
        """
        create an in-memory reference mesh with layer manager initialized;
        this mesh and layer info can be accessed later by setting target mesh to
        MllInterface.TARGET_REFERENCE_MESH.

        :param list vertices: a float array, listing x y z for first vertex, then second, etc;
        :param list triangles: an int array, listing vertex IDs for first triangle, then second, etc.
        """

        self.ngSkinLayerCmd(
            e=True, referenceMeshVertices=self.__floatListAsString(vertices), referenceMeshTriangles=self.__intListAsString(triangles)
        )

    def getReferenceMeshVerts(self):
        """
        :return: a list of floats, where each three values is a vertex XYZ for reference mesh vertices
        """
        return self.ngSkinLayerCmd(q=True, referenceMeshVertices=True)

    def getReferenceMeshTriangles(self):
        """
        :return: a list of integers, where each three values describe mesh vert IDs that make up a triangle in the reference mesh
        """
        return self.ngSkinLayerCmd(q=True, referenceMeshTriangles=True)

    def getInfluenceLimitPerVertex(self):
        """
        :return: current value of "influence limit per vertex" setting for this mesh. ``0`` is returned when there's no limit.
        """
        return self.ngSkinLayerCmd(q=True, influenceLimitPerVertex=True)

    def setInfluenceLimitPerVertex(self, limit=None):
        """
        Set max number of influences permitted for this mesh/skin cluster. This limit will
        be applied as a post-processing filter, before writing data to skin cluster.

        See ngSkinTools user manual for more info on this mechanic.

        :param int limit: max number of influences allowed; provide ``0`` or ``None`` to remove the limit.
        """
        if limit is None:
            limit = 0
        self.ngSkinLayerCmd(e=True, influenceLimitPerVertex=limit)

    def listInfluenceIndexes(self):
        """
        :return: list of logical indexes for all influences in this skin cluster
        """
        return self.ngSkinLayerCmd(q=True, influenceIndexes=True)

    def listInfluencePaths(self):
        """
        :return: list of influence names for all influences in this skin cluster
        """
        return self.ngSkinLayerCmd(q=True, influencePaths=True)

    def listInfluencePivots(self):
        """
        Returns coordinates for influence pivots for all influences in this skin cluster;

        :return: a list where each element is 3-float tuple, e.g. ```[(1.0,2.0,3.0),(0,0,0),...]```
        """
        influencePivots = self.ngSkinLayerCmd(q=True, influencePivots=True)
        return list(zip(influencePivots[0::3], influencePivots[1::3], influencePivots[2::3]))

    @staticmethod
    def influencesMapToList(influencesMapping):
        return ','.join(str(k) + "," + str(v) for (k, v) in list(influencesMapping.items()))

    def layerMergeDown(self, layerId):
        """
        Merges given layer the layer below it.

        :param int layerId: layer to be merged
        """

        self.ngSkinLayerCmd(e=True, layerId=int(layerId), layerMergeDown=True)

    def getLayerIndex(self, layerId):
        return self.ngSkinLayerCmdMel("-id {0} -q -layerIndex".format(layerId))

    def setLayerIndex(self, layerId, layerIndex):
        self.ngSkinLayerCmd(e=True, id=int(layerId), layerIndex=int(layerIndex))

    def pruneWeights(self, layerId=None, threshold=0.01):
        """
        Remove weights in influence weights lower than provided threshold;
        upscale remaining weights, preserving transparency of the layer.

        :param int layerId: layer to be processed; if not provided, will use currently active layer
        :param float threshold: weights below this value will be set to 0
        """

        self.ngSkinLayerCmd(e=True, layerId=int(layerId), pruneWeights=True, pruneWeightsThreshold=threshold)

    def pruneMask(self, layerId=None, threshold=0.01):
        """
        remove weights in layer mask lower than provided threshold;
        """
        self.ngSkinLayerCmd(e=True, layerId=int(layerId), pruneMask=True, pruneWeightsThreshold=threshold)

    def floodPaint(self):
        self.ngSkinLayerCmd(paintFlood=True)

    def cacheIndexedColors(self):
        for i in range(30):
            c = cmds.colorIndex(i + 1, q=True)
            self.ngSkinLayerCmd(indexedColorIndex=(i + 1), indexedColorValue=self.__floatListAsString(c))

    def getDataNode(self):
        return self.ngSkinLayerCmd(q=True, layerDataNode=True)


class BatchUpdateContext(Object):
    """
    A helper class for MllInterface.batchUpdateContext() method, helping
    implement "with" statement setup/teardown functionality
    """

    def __init__(self, mll):
        self.mll = mll

    def __enter__(self):
        self.mll.beginDataUpdate()
        return self.mll

    def __exit__(self, _type, value, traceback):
        self.mll.endDataUpdate()
