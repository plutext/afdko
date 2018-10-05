from fontTools.misc.py23 import BytesIO
from fontTools.cffLib import (TopDictIndex,
                              buildOrder,
                              topDictOperators,
                              topDictOperators2,
                              privateDictOperators,
                              privateDictOperators2,
                              FDArrayIndex,
                              FontDict,
                              VarStoreData,)
from fontTools.ttLib import newTable
from fontTools import varLib
from cff2mergePen import CFF2CharStringMergePen


def addCFFVarStore(varModel, varFont):
    supports = varModel.supports[1:]
    fvarTable = varFont['fvar']
    axisKeys = [axis.axisTag for axis in fvarTable.axes]
    varTupleList = varLib.builder.buildVarRegionList(supports, axisKeys)
    varTupleIndexes = list(range(len(supports)))
    varDeltasCFFV = varLib.builder.buildVarData(varTupleIndexes, None, False)
    varStoreCFFV = varLib.builder.buildVarStore(varTupleList, [varDeltasCFFV])

    topDict = varFont['CFF2'].cff.topDictIndex[0]
    topDict.VarStore = VarStoreData(otVarStore=varStoreCFFV)


def addNamesToPost(ttFont, fontGlyphList):
    postTable = ttFont['post']
    postTable.glyphOrder = ttFont.glyphOrder = fontGlyphList
    postTable.formatType = 2.0
    postTable.extraNames = []
    postTable.mapping = {}
    postTable.compile(ttFont)


def lib_convertCFFToCFF2(cff, otFont):
    # This assumes a decompiled CFF table.
    cff2GetGlyphOrder = cff.otFont.getGlyphOrder
    topDictData = TopDictIndex(None, cff2GetGlyphOrder, None)
    topDictData.items = cff.topDictIndex.items
    cff.topDictIndex = topDictData
    topDict = topDictData[0]
    if hasattr(topDict, 'Private'):
        privateDict = topDict.Private
    else:
        privateDict = None
    opOrder = buildOrder(topDictOperators2)
    topDict.order = opOrder
    topDict.cff2GetGlyphOrder = cff2GetGlyphOrder
    if not hasattr(topDict, "FDArray"):
        fdArray = topDict.FDArray = FDArrayIndex()
        fdArray.strings = None
        fdArray.GlobalSubrs = topDict.GlobalSubrs
        topDict.GlobalSubrs.fdArray = fdArray
        charStrings = topDict.CharStrings
        if charStrings.charStringsAreIndexed:
            charStrings.charStringsIndex.fdArray = fdArray
        else:
            charStrings.fdArray = fdArray
        fontDict = FontDict()
        fontDict.setCFF2(True)
        fdArray.append(fontDict)
        fontDict.Private = privateDict
        privateOpOrder = buildOrder(privateDictOperators2)
        for entry in privateDictOperators:
            key = entry[1]
            if key not in privateOpOrder:
                if key in privateDict.rawDict:
                    # print "Removing private dict", key
                    del privateDict.rawDict[key]
                if hasattr(privateDict, key):
                    delattr(privateDict, key)
                    # print "Removing privateDict attr", key
    else:
        # clean up the PrivateDicts in the fdArray
        fdArray = topDict.FDArray
        privateOpOrder = buildOrder(privateDictOperators2)
        for fontDict in fdArray:
            fontDict.setCFF2(True)
            for key in fontDict.rawDict.keys():
                if key not in fontDict.order:
                    del fontDict.rawDict[key]
                    if hasattr(fontDict, key):
                        delattr(fontDict, key)

            privateDict = fontDict.Private
            for entry in privateDictOperators:
                key = entry[1]
                if key not in privateOpOrder:
                    if key in privateDict.rawDict:
                        # print "Removing private dict", key
                        del privateDict.rawDict[key]
                    if hasattr(privateDict, key):
                        delattr(privateDict, key)
                        # print "Removing privateDict attr", key
    # Now delete up the decrecated topDict operators from CFF 1.0
    for entry in topDictOperators:
        key = entry[1]
        if key not in opOrder:
            if key in topDict.rawDict:
                del topDict.rawDict[key]
            if hasattr(topDict, key):
                delattr(topDict, key)

    # At this point, the Subrs and Charstrings are all still T2Charstring class
    # easiest to fix this by compiling, then decompiling again
    cff.major = 2
    file = BytesIO()
    cff.compile(file, otFont, isCFF2=True)
    file.seek(0)
    cff.decompile(file, otFont, isCFF2=True)


def convertCFFtoCFF2(varFont):
    # base font contains the CFF2 blend data, but with the table tag 'CFF '
    # all the CFF fields. Remove all the fields that were removed in the
    # CFF2 spec.

    cffTable = varFont['CFF ']
    lib_convertCFFToCFF2(cffTable.cff, varFont)
    newCFF2 = newTable("CFF2")
    newCFF2.cff = cffTable.cff
    varFont['CFF2'] = newCFF2
    del varFont['CFF ']


def merge_charstrings(default_charstrings,
                      glyphOrder,
                      num_masters,
                      region_fonts):
    for gname in glyphOrder:
        default_charstring = default_charstrings[gname]
        var_pen = CFF2CharStringMergePen([], num_masters, master_idx=0)
        default_charstring.draw(var_pen)
        region_idx = 0
        for ttFont in region_fonts:
            region_idx += 1
            region_charstrings = ttFont['CFF '].cff.topDictIndex[0].CharStrings
            region_charstring = region_charstrings[gname]
            var_pen.restart(region_idx)
            region_charstring.draw(var_pen)
        new_charstring = var_pen.getCharString(
            private=default_charstring.private,
            globalSubrs=default_charstring.globalSubrs,
            optimize=False)
        default_charstrings[gname] = new_charstring
