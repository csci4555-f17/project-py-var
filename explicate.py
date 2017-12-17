
import ast
from functools import reduce

import extendedast as ext
import constants as C


class Explicator(ast.NodeTransformer):

    def __init__(self):
        self._free_var_ctr = 0

    def visit_Module(self, module):
        module = self.generic_visit(module)
        return ast.copy_location(ast.Module([ast.Call(ast.Lambda(
            ast.arguments([], None, [], None, [], []),
            module.body
        ), [], [])]), module)

    def visit_UnaryOp(self, uop):
        uop = self.generic_visit(uop)

        if isinstance(uop.op, ast.USub):
            tag = C.T_INT
        elif isinstance(uop.op, ast.Not):
            tag = C.T_BOOL
            operand = self._free_var()
            uop.operand = ext.Tag(ext.Let(
                operand, uop.operand, test_truthy(operand)
            ), C.T_BOOL)
        else:
            raise NotImplementedError(
                "unary operator '{}'".format(ast.dump(uop.op))
            )

        operand = self._free_var()
        return ast.copy_location(ext.Let(operand, uop.operand, ast.IfExp(
            ext.CmpEq(ext.GetTag(operand), C.AST_T_BIG),
            ext.TypeConflict(uop.op, [ext.GetTag(operand)]),
            ext.Tag(ast.UnaryOp(uop.op, ext.UnTag(operand, tag)), tag)
        )), uop)

    def visit_BinOp(self, bop):
        bop = self.generic_visit(bop)

        if not isinstance(bop.op, ast.Add):
            raise NotImplementedError(bop.op)

        if C.DEBUG_WITHOUT_EXPLICATE:
            return ext.Tag(ast.BinOp(
                ext.UnTag(bop.left, C.T_INT),
                ast.Add(),
                ext.UnTag(bop.right, C.T_INT)
            ), C.T_INT)

        return ast.copy_location(self._valid_bin_op(
            bop.op, bop.left, bop.right,
            ifbig=lambda left, right: ext.Tag(ast.Call(
                ast.Name('__add', ast.Load()),
                [ext.UnTag(left, C.T_BIG), ext.UnTag(right, C.T_BIG)],
                []
            ), C.T_BIG),
            orelse=lambda left, right: ext.Tag(ast.BinOp(
                ext.UnTag(left, C.T_INT), ast.Add(), ext.UnTag(right, C.T_INT)
            ), C.T_INT)
        ), bop)

    def visit_BoolOp(self, bop):
        bop.values[0] = self.visit(bop.values[0])

        if len(bop.values) == 1:
            return bop.values[0]

        left = self._free_var()

        if isinstance(bop.op, ast.Or):
            test = left
        else:
            test = ast.UnaryOp(ast.Not(), left)

        return ast.copy_location(ext.Let(
            left, bop.values[0], self.visit(  # recursion!
                ast.IfExp(
                    test,
                    left,
                    ast.copy_location(
                        ast.BoolOp(bop.op, bop.values[1:]), bop.values[1]
                    )
                )
            )
        ), bop)

    def visit_IfExp(self, ifexp):
        ifexp = self.generic_visit(ifexp)

        test = self._free_var()
        return ast.copy_location(ext.Let(test, ifexp.test, ast.IfExp(
            test_truthy(test),
            ifexp.body,
            ifexp.orelse
        )), ifexp)

    def visit_While(self, whl):
        whl = self.generic_visit(whl)
        whl.test = test_truthy(whl.test)
        return whl

    def visit_Compare(self, cmp):
        cmp = self.generic_visit(cmp)
        cmp_chain, _ = reduce(
            self._chain_compators,
            zip(cmp.ops, cmp.comparators),
            ([], cmp.left)
        )
        return ast.copy_location(ext.Tag(ast.BoolOp(
            ast.And(), cmp_chain
        ), C.T_BOOL), cmp)

    def visit_Lambda(self, lda):
        lda = self.generic_visit(lda)
        lda.body = [ast.Return(lda.body)]
        return lda

    def visit_FunctionDef(self, func):
        func = self.generic_visit(func)
        return ast.copy_location(ast.Assign(
            [ast.Name(func.name, ast.Store())],
            ast.copy_location(ast.Lambda(func.args, func.body), func)
        ), func)

    def _chain_compators(self, state, op_cmp):
        chain, left = state
        op, right = op_cmp

        if isinstance(op, (ast.Eq, ast.Is, ast.NotEq, ast.IsNot)):
            negated = isinstance(op, (ast.NotEq, ast.IsNot))

            if isinstance(op, (ast.Is, ast.IsNot)):
                res = ext.CmpEq(left, right, negated=negated)
            elif C.DEBUG_WITHOUT_EXPLICATE:
                # treat as int
                res = ext.CmpEq(
                    ext.UnTag(left, C.T_INT),
                    ext.UnTag(right, C.T_INT),
                    negated=negated
                )
            else:
                res = self._valid_bin_op(
                    op, left, right,
                    ifbig=lambda left, right: ast.Call(
                        ast.Name(
                            '__not_equal' if negated else '__equal', ast.Load()
                        ),
                        [ext.UnTag(left, C.T_BIG), ext.UnTag(right, C.T_BIG)],
                        []
                    ),
                    orelse=lambda left, right: ext.CmpEq(
                        ext.UnTag(left, C.T_INT),
                        ext.UnTag(right, C.T_INT),
                        negated=negated
                    )
                )
        else:
            # a < b = a < b
            # a > b = b < a
            # a <= b = !(b < a)
            # a >= b = !(a < b)
            negated = isinstance(op, (ast.LtE, ast.GtE))
            if isinstance(op, (ast.Gt, ast.LtE)):
                left, right = right, left

            if C.DEBUG_WITHOUT_EXPLICATE:
                res = ext.CmpLt(
                        ext.UnTag(left, C.T_INT),
                        ext.UnTag(right, C.T_INT),
                        negated=negated
                )
            else:
                res = self._valid_bin_op(
                    op, left, right,
                    ifbig=lambda left, right: ext.TypeConflict(
                        op, [ext.GetTag(left), ext.GetTag(right)]
                    ),
                    orelse=lambda left, right: ext.CmpLt(
                        ext.UnTag(left, C.T_INT),
                        ext.UnTag(right, C.T_INT),
                        negated=negated
                    )
                )

        chain.append(ast.copy_location(res, op))
        return chain, right

    def _valid_bin_op(self, op, left, right, ifbig, orelse):
        tl, tr = self._free_var(), self._free_var()

        def test_big(bop, items):
            return ast.BoolOp(
                bop, [ext.CmpEq(ext.GetTag(t), C.AST_T_BIG) for t in (tl, tr)]
            )

        return ext.Let(tl, left, ext.Let(tr, right, ast.IfExp(
            test_big(ast.And(), (tl, tr)),
            ifbig(tl, tr),
            ast.IfExp(
                test_big(ast.Or(), (tl, tr)),
                ext.TypeConflict(op, [ext.GetTag(tl), ext.GetTag(tr)]),
                orelse(tl, tr)
            )
        )))

    def _free_var(self):
        self._free_var_ctr += 1
        return ext.Name("#exp{}".format(self._free_var_ctr))


def test_truthy(name):
    return ast.IfExp(
        ext.CmpEq(ext.GetTag(name), C.AST_T_BIG),
        ast.Call(ast.Name('__is_true', ast.Load()), [name], []),
        ext.CmpEq(ext.UnTag(name, C.T_INT), ext.Const(0), negated=True)
    )
