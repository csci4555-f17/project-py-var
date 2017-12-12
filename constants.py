
import x86ir as x86
import extendedast as ext

from extendedast import BuiltinFunction

BUILTIN_FUNCS = {
    'print': BuiltinFunction('print_any', returns=False),
    'input': BuiltinFunction('input_int', returns=True),
    '__add': BuiltinFunction('add', returns=True),
    '__is_true': BuiltinFunction('is_true', returns=True),
    '__equal': BuiltinFunction('equal', returns=True),
    '__not_equal': BuiltinFunction('not_equal', returns=True),
    '__create_list': BuiltinFunction('create_list', returns=True),
    '__create_dict': BuiltinFunction('create_dict', returns=True),
    '__get_subscript': BuiltinFunction('get_subscript', returns=True),
    '__set_subscript': BuiltinFunction('set_subscript', returns=True),
    '__create_closure': BuiltinFunction('create_closure', returns=True),
    '__get_fun_ptr': BuiltinFunction('get_fun_ptr', returns=True),
    '__get_free_vars': BuiltinFunction('get_free_vars', returns=True),
    '__abort': BuiltinFunction('abort', returns=False)
}

TAG_MASK = 0b11
TAG_SHIFT = 2  # bits

T_INT = 0b00
T_BOOL = 0b01
T_BIG = 0b11


AST_TAG_MASK = ext.Const(TAG_MASK)
AST_TAG_SHIFT = ext.Const(TAG_SHIFT)

AST_T_INT = ext.Const(T_INT)
AST_T_BOOL = ext.Const(T_BOOL)
AST_T_BIG = ext.Const(T_BIG)


CSAVE_REGS = set(ext.Reg(r) for r in ("eax", "ecx", "edx"))  # caller save
REGS = [ext.Reg(r) for r in ("eax", "ebx", "ecx", "edx", "esi", "edi")]
CALLEE_SAVE_REGS = list(set(REGS) - CSAVE_REGS)

N_REGS = N_REGS_32 = len(REGS)
N_REGS_8 = 4

INSTANTIATING_INSTRUCTIONS = (
    x86.Mov,
    x86.Sete,
    x86.Setne,
    x86.Pop
)

MODIFYING_INSTRUCTIONS = (
    x86.Add,
    x86.Sub,
    x86.Neg,
    x86.Sar,
    x86.Sal,
    x86.And,
    x86.Or,
    x86.Xor
)
