
import ast

import constants as C
import extendedast as ext
import x86ir as x86
from defunctioning import return_label


def flatten(node):
    if isinstance(node, (x86.X86Instruction, x86.If, x86.While)):
        return [node], node.args[-1]
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
        if isinstance(target, (ast.Name, ext.Name)):
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

        args = []
        for stmts, tmp in (flatten(a) for a in call.args):
            assembly.extend(stmts)
            args.append(tmp)

        assembly.extend(x86.Push(a) for a in reversed(args))

        assembly.append(x86.Call(func))
        if args:
            assembly.append(x86.Add(ext.Const(4*len(args)), ext.Reg('esp')))

    else:
        assembly = [x86.Add(ext.Const(0), ext.Reg('esi'))]
        asmcls, closure = flatten(call.func)
        assembly += asmcls

        asmfunc, func = flatten(
            ast.Call(ast.Name('__get_fun_ptr', ast.Load()), [closure], [])
        )
        assembly += asmfunc

        call.args = (
            [ast.Call(ast.Name('__get_free_vars', ast.Load()), [closure], [])]
            + call.args
        )

        starargs = [a.value for a in call.args if isinstance(a, ast.Starred)]
        minargs = len(call.args) - len(starargs)

        nargs = _free_var(fname='vdic')
        assembly.append(x86.Mov(C.ConstInt(minargs), nargs))
        for arg in starargs:
            stmts, tmp = flatten(ast.Call(
                ast.Name('len', ast.Load()), [arg], []
            ))
            assembly += stmts
            assembly.append(x86.Add(tmp, nargs))

        asmnpars, nparams = flatten(ast.Call(
            ast.Name('__get_nparams', ast.Load()), [closure], []
        ))
        assembly += asmnpars

        nvarargs = _free_var(fname='vdic')
        assembly += [
            # no need to untag, since T_INT is 0b00
            x86.Mov(nargs, nvarargs),
            x86.Sub(nparams, nvarargs),
        ] + flatten(ext.Inc(nparams))[0]

        asmargs, argl = flatten(ext.Tag(ast.Call(
            ast.Name('__create_list', ast.Load()), [nparams], []
        ), C.T_BIG))
        assembly += asmargs

        assembly += flatten(ext.Dec(nparams))[0]

        assembly += flatten(ast.Assign(
            [ast.Subscript(argl, nparams, ast.Store())],
            ext.Tag(ast.Call(
                ast.Name('__create_list', ast.Load()), [nvarargs], []
            ), C.T_BIG)
        ))[0]

        itr = _free_var(fname='vdic')
        assembly += flatten(ast.Assign([itr], C.AST_CONST_0))[0]

        for arg in call.args:
            if isinstance(arg, ast.Starred):
                asmarg, arg = flatten(arg.value)
                assembly += asmarg

                i2 = _free_var(fname='vdic')
                assembly += flatten(ast.Assign([i2], C.AST_CONST_0))[0]

                asmmax, maxi2 = flatten(
                    ast.Call(ast.Name('len', ast.Load()), [arg], [])
                )
                assembly += asmmax

                lst, pos = _free_var(fname='vdic'), _free_var(fname='vdic')
                assembly += flatten(ast.While(ext.CmpLt(i2, maxi2), [
                    ast.Assign([lst], ast.IfExp(
                        ext.CmpLt(itr, nparams),
                        argl,
                        ast.Subscript(argl, nparams, ast.Load)
                    )),
                    ast.Assign([pos], ast.IfExp(
                        ext.CmpLt(itr, nparams),
                        itr,
                        ast.BinOp(itr, ast.Sub(), nparams)
                    )),
                    ast.Assign(
                        [ast.Subscript(lst, ast.Index(pos), ast.Store())],
                        ast.Subscript(arg, ast.Index(i2), ast.Load())
                    ),
                    ext.Inc(itr),
                    ext.Inc(i2)
                ], []))[0]

            else:
                lst, pos = _free_var(fname='vdic'), _free_var(fname='vdic')
                assembly += [inst for node in (
                    ast.Assign([lst], ast.IfExp(
                       ext.CmpLt(itr, nparams),
                       argl,
                       ast.Subscript(argl, nparams, ast.Load)
                    )),
                    ast.Assign([pos], ast.IfExp(
                       ext.CmpLt(itr, nparams),
                       itr,
                       ast.BinOp(itr, ast.Sub(), nparams)
                    )),
                    ast.Assign(
                        [ast.Subscript(lst, ast.Index(pos), ast.Store())], arg
                    ),
                    ext.Inc(itr)
                ) for inst in flatten(node)[0]]

        assembly += flatten(ast.Assign(
            [itr], ast.BinOp(nparams, ast.Add(), C.ConstInt(1))
        ))[0]

        tmp = _free_var(fname='vdic')
        assembly += flatten(ast.While(ext.CmpLt(C.AST_CONST_0, itr), [
            ext.Dec(itr),
            ast.Assign(
                [tmp],
                ast.Subscript(argl, ast.Index(itr), ast.Load())
            ),
            x86.Push(tmp)  # mixing x86 and AST!
        ], []))[0]

        assembly += [
            x86.CallPtr(func),
            # nparams is a tagged int, meaning that since T_INT = 0b00,
            # nparams = 4 * n_args_untagged. Thus we can do the trick below:
            x86.Add(nparams, ext.Reg('esp'))
        ]

    # print(func, args)

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
        op = x86.Add
    elif isinstance(bop.op, ast.Sub):
        op = x86.Sub
    else:
        return flatten_error(bop)

    left, tl = flatten(bop.left)
    right, tr = flatten(bop.right)
    res = _free_var(fname='biop')
    return left + right + [
        x86.Mov(tl, res),
        op(tr, res)
    ], res


def flatten_Inc(inc):
    return [x86.Add(ext.Const(0b100), inc.value)], inc.value
    # return flatten(ast.Assign([inc.value], ext.Tag(ast.BinOp(
    #     ext.UnTag(inc.value, C.T_INT),
    #     ast.Add(),
    #     ext.Const(1)
    # ), C.T_INT)))


def flatten_Dec(dec):
    return [x86.Add(
        ext.Const((-1 << C.TAG_SHIFT) | C.T_INT),
        dec.value
    )], dec.value
    # return flatten(ast.Assign([dec.value], ext.Tag(ast.BinOp(
    #     ext.UnTag(dec.value, C.T_INT),
    #     ast.Add(),
    #     ext.Const(-1)
    # ), C.T_INT)))


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
        ops = (x86.Setg, x86.Setng)
    else:
        ops = (x86.Setl, x86.Setnl)

    tuns = _free_var(fname='clt', max_color=C.N_REGS_8)
    return left + right + [
        x86.Cmp(tr, tl),
        ops[clt.negated](tuns),
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
            [ast.Subscript(tret, ast.Index(ast.Num(i)), ast.Store())], e
        ))[0])
    return assembly, tret


def flatten_Dict(dct):
    assembly, tret = flatten(ext.Tag(ast.Call(
        ast.Name('__create_dict', ast.Load()), [], []
    ), C.T_BIG))
    for k, v in zip(dct.keys, dct.values):
        assembly.extend(flatten(ast.Assign(
            [ast.Subscript(tret, ast.Index(k), ast.Store())], v
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
