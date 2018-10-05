# Copyright (c) 2009 Type Supply LLC

from __future__ import print_function, division, absolute_import
from fontTools.misc.psCharStrings import T2CharString
from fontTools.pens.t2CharStringPen import T2CharStringPen


class MergeTypeError(TypeError):
    def __init__(self, region_type, pt_index, m_index, default_type):
        error_msg = """{region_type} at point index {pt_index} in master"
{m_index}' differs from the default font point "
type {default_type}""".format(
                                        region_type=region_type,
                                        pt_index=pt_index,
                                        m_index=m_index,
                                        default_type=default_type)

        super(MergeTypeError, self).__init__(error_msg)


def commandsToProgram(commands):
    """Takes a commands list as returned by programToCommands() and converts
    it back to a T2CharString program list."""
    program = []
    for op, args in commands:
        for arg in args:
            if type(arg) is tuple:
                program.append(arg[0])
                program.extend([argn - arg[0] for argn in arg[1:]])
                program.append(1)
                program.append('blend')
            else:
                program.append(arg)
        if op:
            program.append(op)
    return program


class CFF2CharStringMergePen(T2CharStringPen):
    """Pen to merge Type 2 CharStrings.
    """
    def __init__(self, default_commands, num_masters, master_idx):
        super(
            CFF2CharStringMergePen,
            self).__init__(width=None, glyphSet=None, CFF2=True)
        self.pt_index = 0
        self._commands = default_commands
        self.m_index = master_idx
        self.num_masters = num_masters

    def _p(self, pt):
        p0 = self._p0
        pt = self._p0 = self.roundPoint(pt)
        return [pt[0]-p0[0], pt[1]-p0[1]]

    def add_point(self, region_type, pt_coords):

        if self.m_index == 0:
            self._commands.append([region_type, [pt_coords]])
        else:
            cmd = self._commands[self.pt_index]
            if cmd[0] != region_type:
                raise MergeTypeError(
                                region_type,
                                self.pt_index,
                                len(cmd[1]),
                                cmd[0])
            cmd[1].append(pt_coords)
        self.pt_index += 1

    def _moveTo(self, pt):
        pt_coords = self._p(pt)
        self.add_point('rmoveto', pt_coords)

    def _lineTo(self, pt):
        pt_coords = self._p(pt)
        self.add_point('rlineto', pt_coords)

    def _curveToOne(self, pt1, pt2, pt3):
        _p = self._p
        pt_coords = _p(pt1)+_p(pt2)+_p(pt3)
        self.add_point('rrcurveto', pt_coords)

    def _closePath(self):
        pass

    def _endPath(self):
        pass

    def restart(self, region_idx):
        self.pt_index = 0
        self.m_index = region_idx
        self._p0 = (0,0)
        
    def getCommands(self):
        return self._commands

    def addBlendOps(self):
        for cmd in self._commands:
            # arg[i] is the set of arguments for this operator from master i.
            args = cmd[1]
            m_args = zip(*args)
            # m_args[n] is now all num_master args for the ith argument
            # for this operation.
            cmd[1] = m_args
            # reduce the variable args to a non-variable arg
            # if the values are all the same.
            for i, arg in enumerate(m_args):
                if max(arg) == min(arg):
                    m_args[i] = arg[0]
            cmd[1] = m_args

    def getCharString(self, private=None, globalSubrs=None, optimize=True):
        self.addBlendOps()
        program = commandsToProgram(self._commands)
        charString = T2CharString(
            program=program, private=private, globalSubrs=globalSubrs)
        return charString
