
import ast
import sys
from collections import namedtuple

BuiltinFunction = namedtuple('BuiltinFunction', ['id', 'returns'])


class Reg(namedtuple('Reg', ['id'])):
    def __repr__(self):
        return "%{}".format(self.id)


class Const(namedtuple('Const', ['value'])):
    def __repr__(self):
        return "${}".format(self.value)


class Name(namedtuple('Name', ['id', 'max_color'])):
    def __repr__(self):
        return self.id


Name.ANY_COLOR = sys.maxsize
Name.__new__.__defaults__ = (Name.ANY_COLOR,)


def ExAstNode(name, fields):
    class EAstNode(ast.AST):
        pass
    EAstNode.__name__ = name
    EAstNode._fields = fields

    return EAstNode


Let = ExAstNode('Let', ['name', 'expr', 'body'])
GetTag = ExAstNode('GetTag', ['expr'])
Tag = ExAstNode('Tag', ['expr', 'tag'])
UnTag = ExAstNode('UnTag', ['expr', 'tag'])
TypeConflict = ExAstNode('TypeConflict', ['op', 'types'])
Return = ExAstNode('Return', ['value', 'func_name'])

Function = ExAstNode('Function', ['name', 'args', 'body'])


class Closure(
    ExAstNode('Closure', ['func', 'free_vars', 'nargs', 'variadic'])
):
    def __repr__(self):
        return "{}<>".format(self.func, ', '.join(map(str, self.free_vars)))

    def __str__(self):
        return self.func


class CmpEq(ExAstNode('CmpEq', ['left', 'right', 'negated'])):
    def __init__(self, left, right, negated=False):
        super().__init__(left, right, negated)


class CmpLt(ExAstNode('CmpLt', ['left', 'right', 'negated'])):
    def __init__(self, left, right, negated=False):
        super().__init__(left, right, negated)


Inc = ExAstNode('Inc', ['value'])
Dec = ExAstNode('Dec', ['value'])
