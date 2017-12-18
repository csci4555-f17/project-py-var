
import ast
from collections import defaultdict

from constants import BUILTIN_FUNCS


class Uniqifier(ast.NodeTransformer):

    def __init__(self):
        self._stack = defaultdict(list)
        self._ctr = 0

    def visit_Assign(self, assign):
        return self._visit_last(assign, 'targets')

    def visit_Call(self, call):
        return self._visit_last(call, 'func')

    def visit_Name(self, name):
        if isinstance(name.ctx, ast.Load):
            try:
                name.id = self._scoped_name(name.id)
            except KeyError:
                if name.id not in BUILTIN_FUNCS:
                    raise
        # comment next two lines for static typing
        elif self._stack[name.id] and self._stack[name.id][-1] != -1:
            name.id = self._scoped_name(name.id)
        else:
            name.id = self._push_name(name.id)
        return name

    def visit_arg(self, arg):
        arg.arg = self._push_name(arg.arg)
        return arg

    def visit_FunctionDef(self, func):
        func.name = self._push_name(func.name)
        return self._visit_new_scope(func)

    def visit_Lambda(self, lda):
        return self._visit_new_scope(lda)

    def _visit_new_scope(self, func_like):
        self._push_frame()
        func_like = self.generic_visit(func_like)
        self._pop_frame()
        return func_like

    def _scoped_name(self, name):
        return self._to_scoped_name(name, self._scoped_id(name))

    def _push_name(self, name):
        try:
            sid = self._scoped_id(name)
        except KeyError:
            sid = 0
        new_id = self._new_id(sid)
        self._stack[name].append(new_id)
        return self._to_scoped_name(name, new_id)

    def _scoped_id(self, name):
        stack = self._stack[name]
        for uid in reversed(stack):
            if uid != -1:
                # if stack[-1] == -1:
                #     stack.append(uid)  # optimization to speed up searching
                return uid
        raise KeyError("name '{}' not in scope".format(name))

    def _push_frame(self):
        for name, stack in self._stack.items():
            stack.append(-1)

    def _pop_frame(self):
        for name, stack in self._stack.items():
            while stack and stack.pop() != -1:
                pass

    def _to_scoped_name(self, name, uid):
        return '{}_{}'.format(name, uid)

    def _new_id(self, old_id):
        self._ctr += 1
        return self._ctr

    def _visit_last(self, node, field):
        for f in (f for f, _ in ast.iter_fields(node) if f != field):
            self._visit_field(node, f)
        self._visit_field(node, field)
        return node

    def _visit_field(self, node, field):
        value = getattr(node, field)
        if isinstance(value, list):
            for i, v in enumerate(value):
                value[i] = self.visit(value[i])
        else:
            setattr(node, field, self.visit(value))
