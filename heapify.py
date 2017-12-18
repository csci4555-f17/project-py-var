
import ast
from constants import BUILTIN_FUNCS


class FreeVarFinder(ast.NodeVisitor):

    def __init__(self):
        self.f_vars = set()

    def visit_Lambda(self, lda):
        self.generic_visit(lda)

        visitor = LocalFreeVarFinder()
        visitor.visit(lda)
        self.f_vars |= visitor.free_vars()

    def free_vars(self):
        return self.f_vars


class LocalFreeVarFinder(ast.NodeVisitor):

    def __init__(self):
        self.f_vars = set()
        self.l_vars = set()
        self.p_vars = set()

    def visit_Lambda(self, lda):
        self.p_vars |= set((a.arg for a in lda.args.args))
        if lda.args.vararg:
            self.p_vars.add(lda.args.vararg.arg)
        self.generic_visit(lda)

    def visit_Name(self, name):
        local_vars = self.l_vars | self.p_vars | set(BUILTIN_FUNCS.keys())

        if isinstance(name.ctx, ast.Load):
            if name.id not in local_vars:
                self.f_vars.add(name.id)

        elif isinstance(name.ctx, ast.Store):
            self.l_vars.add(name.id)
            self.f_vars.discard(name.id)

    def free_vars(self):
        return set(self.f_vars)

    def param_vars(self):
        return set(self.p_vars)

    def local_vars(self):
        return set(self.l_vars)


def free_vars(n):
    visitor = FreeVarFinder()
    visitor.visit(n)
    return visitor.free_vars()


class Heapifier(ast.NodeTransformer):

    def __init__(self, free_vars):
        self.free_vars = free_vars

    def visit_Lambda(self, lda):
        visitor = LocalFreeVarFinder()
        visitor.visit(lda)

        lda = self.generic_visit(lda)

        setattr(lda, 'free_vars', visitor.free_vars())

        free_params = [
            arg.arg for arg in lda.args.args if arg.arg in self.free_vars
        ]

        for arg in lda.args.args:
            if arg.arg in free_params:
                arg.arg = self.heapified_param_name(arg.arg)

        if lda.args.vararg and lda.args.vararg.arg in self.free_vars:
            free_params.append(lda.args.vararg.arg)
            lda.args.vararg.arg = self.heapified_param_name(lda.args.vararg.arg)

        lda.body = [
            ast.Assign(
                [ast.Name(name, ast.Store())],
                ast.List([
                    ast.Name(self.heapified_param_name(name), ast.Load())
                ], ast.Load())
            )
            for name in free_params
        ] + [
            ast.Assign(
                [ast.Name(name, ast.Store())],
                ast.List([ast.Num(0)], ast.Load())
            )
            for name in visitor.local_vars() if name in self.free_vars
        ] + lda.body

        # for arg in lda.args:
        #     if arg in self.free_vars:
        #         free_params.append(arg)

        return lda

    def visit_Name(self, name):
        return name if (name.id not in self.free_vars) else \
            ast.copy_location(ast.Subscript(
                ast.Name(name.id, ast.Load()),
                ast.Index(ast.Num(0)),
                name.ctx
            ), name)

    def heapified_param_name(self, pid):
        return pid + '_h'


def heapify_free_vars(node):
    return Heapifier(free_vars(node)).visit(node)


# def heapify(node):
#     fname = 'heapify_{}'.format(node.__class__.__name__)
#     func = globals.get(fname, heapify_error)
#     vars_to_heapify = free_vars(node)
#     return func(node, vars_to_heapify)
#
#
# def heapify_error(node):
#     context = ""
#     if hasattr(node, 'lineno') and hasattr(node, 'col_offset'):
#         context = "@({}:{})".format(node.lineno, node.col_offset)
#     detail = ast.dump(node) if isinstance(node, ast.AST) else str(node)
#     raise NotImplementedError("could not heapify {}{}: {}".format(
#         node.__class__, context, detail
#     ))
