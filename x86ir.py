
import textwrap
from collections import namedtuple

import extendedast as ext


class X86Instruction:

    def __init__(
        self, *args, op=None, reg_modifier=None,
        read_args=None, written_args=None
    ):
        self.op = op
        self.reg_mod = reg_modifier
        self.args = list(args)
        self.rargs = set(read_args or [])
        self.wargs = set(written_args or [])

    def read_args(self):
        return self.get_vars(self.rargs)

    def written_args(self):
        return self.get_vars(self.wargs)

    def get_vars(self, indices):
        return set(
            self.args[i] for i in indices if isinstance(self.args[i], ext.Name)
        )

    def _reg_modded_args(self):
        return self.args if not self.reg_mod else [
            ext.Reg(self.reg_mod(a.id)) if isinstance(a, ext.Reg) else a
            for a in self.args
        ]

    def __str__(self):
        args = self._reg_modded_args()
        return "    {} {}".format(self.op, ', '.join(str(a) for a in args))

    def __repr__(self):
        args = self._reg_modded_args()
        return "{} {}".format(self.op, ' '.join(repr(a) for a in args))

    @classmethod
    def copy(cls, obj):
        return obj.__class__(*obj.args)


def X86Op(op, reg_modifier=None, read_args=None, written_args=None):

    class Op(X86Instruction):

        def __init__(self, *args):
            super().__init__(
                *args, op=op, reg_modifier=reg_modifier,
                read_args=read_args, written_args=written_args
            )

    return Op


If = namedtuple('If', ['test', 'body', 'orelse'])


class Directive(namedtuple('Directive', ['name', 'args'])):
    def __str__(self):
        return ".{} {}".format(self.name, ', '.join(map(str, self.args)))


class Label(namedtuple('Label', ['name'])):
    def __str__(self):
        return "{}:".format(self.name)


Mov = X86Op('movl', read_args=[0], written_args=[1])
Add = X86Op('addl', read_args=[0, 1], written_args=[1])
Sub = X86Op('subl', read_args=[0, 1], written_args=[1])
Neg = X86Op('negl', read_args=[0], written_args=[0])

Sal = X86Op('sall', read_args=[0, 1], written_args=[1])
Sar = X86Op('sarl', read_args=[0, 1], written_args=[1])
And = X86Op('andl', read_args=[0, 1], written_args=[1])
Or = X86Op('orl', read_args=[0, 1], written_args=[1])
Xor = X86Op('xorl', read_args=[0, 1], written_args=[1])

Cmp = X86Op('cmpl', read_args=[0, 1])
Jmp = X86Op('jmp', read_args=[0])
Je = X86Op('je', read_args=[0])

Sete = X86Op('sete', reg_modifier=(lambda r: r[1] + 'l'), written_args=[0])
Setne = X86Op('setne', reg_modifier=(lambda r: r[1] + 'l'),
              written_args=[0])

Call = X86Op('call', read_args=[0])


class CallPtr(Call):
    def __str__(self):
        return "    {} *{}".format(self.op, self._reg_modded_args()[0])

    def __repr__(self):
        return "{} *{}".format(self.op, self._reg_modded_args()[0])


Push = X86Op('pushl', read_args=[0])
Pop = X86Op('popl', written_args=[0])

Leave = X86Op('leave')
Ret = X86Op('ret')


def dump(statements):
    text = ""
    for s in statements:
        if isinstance(s, If):
            text += textwrap.dedent("""
                if {}:
                {}
                else:
                {}
            """).lstrip().rstrip().format(
                s.test,
                textwrap.indent(dump(s.body), '    ').rstrip(),
                textwrap.indent(dump(s.orelse), '    ')
            )
        else:
            text += "{}\n".format(repr(s))
    return text
