
import extendedast as ext
import x86ir as x86
from constants import CALLEE_SAVE_REGS


def wrap_function(scoped_block):
    stmts, stack_size = scoped_block.body

    prologue = [
        x86.Directive('align', [16]),
        x86.Label(scoped_block.name),
        x86.Push(ext.Reg('ebp')),
        x86.Mov(ext.Reg('esp'), ext.Reg('ebp')),
    ] + [x86.Push(reg) for reg in CALLEE_SAVE_REGS]
    if stack_size > 0:
        prologue.append(x86.Sub(ext.Const(stack_size), ext.Reg('esp')))

    return prologue + stmts + [
        x86.Mov(ext.Const(0), ext.Reg('eax')),
        x86.Label(return_label(scoped_block.name))
    ] + [x86.Pop(reg) for reg in reversed(CALLEE_SAVE_REGS)] + [
        x86.Leave(),
        x86.Ret()
    ]


def return_label(func_name):
    return "ret_{}".format(func_name)
