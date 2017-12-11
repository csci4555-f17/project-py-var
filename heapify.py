
import ast


def vars_to_heapify(node):
    if isinstance(node, (ast.FunctionDef, ast.Lambda)):
        to_heapify = unset_vars(node.body) - set(node.args)
    
