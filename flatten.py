

import ast

import constants as C
import extendedast as ext
import x86ir as x86
from defunctioning import return_label


def flatten(node):
    fname = 'flatten_{}'.format(node.__class__.__name__)
    func = globals().get(fname, flatten_error)
    return func(node)


# def flatten_Module(module):
#     return [
#         flattened for stmt in module.body for flattened in flatten(stmt)[0]
#     ]


def flatten_Assign(assign):
    assembly, tmp = flatten(assign.value)
    for target in assign.targets:
        if isinstance(target, ast.Name):
            assembly.append(x86.Mov(tmp, ext.Name(target.id)))
        elif isinstance(target, ast.Subscript):
            assembly.extend(flatten(ast.Call(
               ast.Name('__set_subscript', ast.Load()),
               [target.value, target.slice, tmp],
               []
            ))[0])
        else:
            return flatten_error(target)
    return assembly, tmp


def flatten_Expr(expr):
    return flatten(expr.value)


def flatten_Let(let):
    e_assembly, tmpe = flatten(let.expr)
    b_assembly, tmpb = flatten(let.body)
    return e_assembly + [x86.Mov(tmpe, let.name)] + b_assembly, tmpb


def flatten_Call(call):
    if isinstance(call.func, ast.Name) and call.func.id in C.BUILTIN_FUNCS:
        func = C.BUILTIN_FUNCS[call.func.id].id
        assembly = []
        caller = x86.Call
    else:
        assembly, func = flatten(call.func)
        caller = x86.CallPtr

    # argass, argstmp = flatten(ast.List([], ast.Load()))
    # assembly.extend(argass)
    # for arg in call.args:
    #     argass, a2tmp = flatten(ast.List([arg], ast.Load()))
    #     assembly.extend(argass)
    #     argass, argstmp = flatten(ast.Assign(argstmp, ast.BinOp(
    #         argstmp, ast.Add(), a2tmp
    #     )))
    #     assembly.extend(argass)
    #
    # for stmts, tmp in (flatten(a) for a in call.args):
    #     assembly.extend(stmts)
    #     args.append(tmp)

    args = []
    for stmts, tmp in (flatten(a) for a in call.args):
        assembly.extend(stmts)
        args.append(tmp)

    # print(func, args)

    assembly.extend(x86.Push(a) for a in reversed(args))

    assembly.append(caller(func))
    if args:
        assembly.append(x86.Add(ext.Const(4*len(args)), ext.Reg('esp')))

    tmp = ext.Const(0)
    # if f.returns:
    tmp = _free_var(fname='call')
    assembly.append(x86.Mov(ext.Reg('eax'), tmp))

    return assembly, tmp


def flatten_UnaryOp(uop):
    if isinstance(uop.op, ast.USub):
        op = x86.Neg
    elif isinstance(uop.op, ast.Not):
        op = (lambda v: x86.Xor(ext.Const(0b1), v))
    else:
        return flatten_error(uop)

    assembly, tmp = flatten(uop.operand)
    tres = _free_var(fname='uop')
    return assembly + [x86.Mov(tmp, tres), op(tres)], tres


def flatten_BinOp(bop):
    if isinstance(bop.op, ast.Add):
        left, tl = flatten(bop.left)
        right, tr = flatten(bop.right)
        res = _free_var(fname='biop')
        return left + right + [
            x86.Mov(tl, res),
            x86.Add(tr, res)
        ], res
    else:
        return flatten_error(bop)


def flatten_BoolOp(bop):
    assembly, values = [], []
    for v in bop.values:
        a, tmp = flatten(v)
        assembly.extend(a)
        values.append(tmp)

    tmp = _free_var(fname='boop')
    op = x86.And if isinstance(bop.op, ast.And) else x86.Or

    first = True
    for v in values:
        assembly.append(x86.Mov(v, tmp) if first else op(v, tmp))
        first = False

    return assembly, tmp


def flatten_CmpEq(ceq):
    left, tl = flatten(ceq.left)
    right, tr = flatten(ceq.right)

    if isinstance(tl, ext.Const) and isinstance(tr, ext.Const):
        eq = (tl.value == tr.value)
        return flatten(
            ext.UnTag(ast.NameConstant(ceq.negated != eq), C.T_BOOL)
        )
    elif isinstance(tl, ext.Const):
        tl, tr = tr, tl

    tuns = _free_var(fname='ceq', max_color=C.N_REGS_8)
    return left + right + [
        x86.Cmp(tr, tl),
        (x86.Setne if ceq.negated else x86.Sete)(tuns),
        x86.And(ext.Const(0b1), tuns)
    ], tuns


def flatten_CmpLt(clt):
    left, tl = flatten(clt.left)
    right, tr = flatten(clt.right)

    if isinstance(tl, ext.Const) and isinstance(tr, ext.Const):
        lt = (tl.value < tr.value)
        return flatten(
            ext.UnTag(ast.NameConstant(clt.negated != lt), C.T_BOOL)
        )
    elif isinstance(tl, ext.Const):
        tl, tr = tr, tl

    tuns = _free_var(fname='clt', max_color=C.N_REGS_8)
    return left + right + [
        x86.Cmp(tr, tl),
        (x86.Setnl if clt.negated else x86.Setl)(tuns),
        x86.And(ext.Const(0b1), tuns)
    ], tuns


def flatten_IfExp(ifexp):
    assembly, tt = flatten(ifexp.test)

    if isinstance(tt, ext.Const):
        return flatten(ifexp.body if tt.value else ifexp.orelse)

    abody, tb = flatten(ifexp.body)
    aorelse, toe = flatten(ifexp.orelse)
    tret = _free_var(fname='ie')

    abody.append(x86.Mov(tb, tret))
    aorelse.append(x86.Mov(toe, tret))
    assembly.append(x86.If(tt, abody, aorelse))

    return assembly, tret


def flatten_While(whl):
    atest, tt = flatten(whl.test)
    if isinstance(tt, ext.Const) and not tt.value:
        return [], tt
    assembly, tb = [], ext.Const(0)
    for stmt in whl.body:
        asm, tb = flatten(stmt)
        assembly += asm
    return [x86.While(atest, tt, assembly)], tb


def flatten_Subscript(subs):
    return flatten(ast.Call(
        ast.Name('__get_subscript', ast.Load()), [subs.value, subs.slice], []
    ))


def flatten_GetTag(gt):
    assembly, tmp = flatten(gt.expr)
    if isinstance(tmp, ext.Const):
        return [], ext.Const(tmp.value & C.TAG_MASK)

    tret = _free_var(fname='gett')
    return assembly + [
        x86.Mov(tmp, tret),
        x86.And(ext.Const(C.TAG_MASK), tret)
    ], tret


def flatten_Tag(tag):

    assembly, tmp = flatten(tag.expr)
    if isinstance(tmp, ext.Const):
        value = tmp.value
        if not tag.tag == C.T_BIG:
            value = tmp.value << C.TAG_SHIFT
        value |= tag.tag
        tmp = ext.Const(value)
    else:
        tex, tmp = tmp, _free_var(fname='sett')
        assembly.append(x86.Mov(tex, tmp))

        if tag.tag == C.T_BIG:
            assembly.append(x86.Or(C.AST_T_BIG, tmp))
        else:
            assembly.extend([
                x86.Sal(C.AST_TAG_SHIFT, tmp),
                x86.Or(ext.Const(tag.tag), tmp)
            ])

    return assembly, tmp


def flatten_UnTag(tag):
    assembly, tmp = flatten(tag.expr)
    if isinstance(tmp, ext.Const):
        tmp = ext.Const((tmp.value & ~C.TAG_MASK) if tag.tag == C.T_BIG else
                        (tmp.value >> C.TAG_SHIFT))
    else:
        tex, tmp = tmp, _free_var(fname='unt')
        assembly.append(x86.Mov(tex, tmp))

        if tag.tag == C.T_BIG:
            assembly.append(x86.And(ext.Const(~C.TAG_MASK), tmp))
        else:
            assembly.append(x86.Sar(C.AST_TAG_SHIFT, tmp))
    return assembly, tmp


def flatten_Return(ret):
    assembly, tmp = flatten(ret.value)
    return assembly + [
        x86.Mov(tmp, ext.Reg('eax')),
        x86.Jmp(return_label(ret.func_name))
    ], ext.Reg('eax')


def flatten_List(lst):
    assembly, tret = flatten(ext.Tag(ast.Call(
        ast.Name('__create_list', ast.Load()), [ast.Num(len(lst.elts))], []
    ), C.T_BIG))
    for i, e in enumerate(lst.elts):
        assembly.extend(flatten(ast.Assign(
            [ast.Subscript(tret, ast.Index(ast.Num(i)), ast.Load())], e
        ))[0])
    return assembly, tret


def flatten_Dict(dct):
    assembly, tret = flatten(ext.Tag(ast.Call(
        ast.Name('__create_dict', ast.Load()), [], []
    ), C.T_BIG))
    for k, v in zip(dct.keys, dct.values):
        assembly.extend(flatten(ast.Assign(
            [ast.Subscript(tret, ast.Index(k), ast.Load())], v
        ))[0])
    return assembly, tret


def flatten_Closure(closure):
    make_list, lst = flatten_List(ast.List([
        ast.Name(name, ast.Load()) for name in closure.free_vars
    ], ast.Load()))
    create_closure, clsr = flatten(ext.Tag(ast.Call(
        ast.Name('__create_closure', ast.Load()), [
            ext.Const(closure.func),
            lst,
            ext.Tag(ext.Const(closure.nargs), C.T_INT),
            ext.Tag(ext.Const(closure.variadic), C.T_BOOL)
        ], []
    ), C.T_BIG))
    return make_list + create_closure, clsr


def flatten_Index(ind):
    return flatten(ind.value)


def flatten_Name(name):
    return [], ext.Name(name.id)


def flatten_Num(num):
    return [], ext.Const((num.n << C.TAG_SHIFT) | C.T_INT)


def flatten_Const(cst):
    return [], cst


def flatten_NameConstant(nc):
    if nc.value in (True, False):
        return [], ext.Const((nc.value << C.TAG_SHIFT) | C.T_BOOL)
    else:
        raise NotImplementedError("NameConstant '{}'".format(nc.value))


def flatten_TypeConflict(tc):
    return flatten(ast.Call(ast.Name('__abort', ast.Load()), [], []))


def flatten_error(node):
    context = ""
    if hasattr(node, 'lineno') and hasattr(node, 'col_offset'):
        context = "@({}:{})".format(node.lineno, node.col_offset)
    detail = ast.dump(node) if isinstance(node, ast.AST) else str(node)
    raise NotImplementedError("could not flatten {}{}: {}".format(
        node.__class__, context, detail
    ))


def _free_var(fname='', max_color=ext.Name.ANY_COLOR):
    _free_var.ctr += 1
    return ext.Name('#ftn{}_{}'.format(
        '_{}'.format(fname) if fname else '', _free_var.ctr
    ), max_color=max_color)


_free_var.ctr = 0
