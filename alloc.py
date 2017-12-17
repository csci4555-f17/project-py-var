
from collections import Counter, defaultdict

import constants as C
import extendedast as ext
import x86ir as x86


NOT_MEM = -1


def allocate_memory(statements, func_args=None):
    success = False
    while not success:
        graph = interference_graph(statements)
        colors = color_names(graph, func_args)
        statements, success = try_transform(statements, colors)
    # print(colors)
    stack_size = max(0, 4*(max(colors.values()) - C.N_REGS + 1))
    return statements, stack_size


def try_transform(statements, colors):
    new_statements = []
    for i, s in enumerate(statements):
        if isinstance(s, x86.If):

            tcol = colors.get(s.test, NOT_MEM)
            test = s.test if tcol is NOT_MEM else get_mem(tcol)

            body, b_success = try_transform(s.body, colors)
            orelse, o_success = try_transform(s.orelse, colors)
            if not b_success:
                statements[i] = x86.If(s.test, body, s.orelse)
            elif not o_success:
                statements[i] = x86.If(s.test, s.body, orelse)
            else:
                new_statements.append(x86.If(test, body, orelse))
                continue  # avoid returning
            return statements, False

        elif isinstance(s, x86.While):

            tcol = colors.get(s.test, NOT_MEM)
            test = s.test if tcol is NOT_MEM else get_mem(tcol)

            tasm, t_success = try_transform(s.tasm, colors)
            body, b_success = try_transform(s.body, colors)
            if not t_success:
                statements[i] = x86.While(tasm, s.test, s.body)
            elif not b_success:
                statements[i] = x86.While(s.tasm, s.test, body)
            else:
                new_statements.append(x86.While(tasm, test, body))
                continue  # avoid returning
            return statements, False

        else:
            arg_colors = [colors.get(a, NOT_MEM) for a in s.args]
            if sum((n < -1 or n >= C.N_REGS) for n in arg_colors) >= 2:
                # handle multi-spilling (x86 only allows 1 mem-access / instr.)
                tmp = _new_unspillable()
                spill_index = next(
                    i for i, n in enumerate(arg_colors) if n >= C.N_REGS
                )

                # old_s = repr(s)

                spilled_arg = s.args[spill_index]
                statements.insert(i, x86.Mov(spilled_arg, tmp))  # save spilled
                s.args[spill_index] = tmp  # swap spilled with saved value

                # print("spill-handled {} -> {}; {}".format(
                #     old_s, repr(statements[i]), repr(s)
                # ))

                return statements, False
            else:
                s = x86.X86Instruction.copy(s)
                s.args = [
                    # if not variable, keep same, else get_mem
                    s.args[i] if c is NOT_MEM else get_mem(c)
                    for i, c in enumerate(arg_colors)
                ]
                new_statements.append(s)
    return new_statements, True


def get_mem(color):
    return "{}(%ebp)".format(-4*(color)) if color < -1 else (
            C.REGS[color] if color < C.N_REGS else
            "{}(%ebp)".format(-4*(color - C.N_REGS + 1))
    )


def color_names(graph, func_args=None):
    saturations = Counter({n: 0 for n in graph if isinstance(n, ext.Name)})
    for r in C.CSAVE_REGS:
        saturations.update(graph[r])

    colors = defaultdict(lambda: NOT_MEM)
    for i, r in enumerate(C.REGS):
        colors[r] = i

    func_args = func_args or []
    for i, name in enumerate(func_args):
        arg = ext.Name(name)
        colors[arg] = - i - 2
        update_uncolored_neighbors(saturations, colors, graph, arg)
        saturations[arg] = -1

    while saturations:
        common = saturations.most_common()

        name, sat = common[0]
        for nnext, snext in common:
            if sat > snext:
                break
            if name.max_color >= nnext.max_color:
                # switch to the more limited name
                name, sat = nnext, snext

        if sat < 0:
            break

        if colors[name] is NOT_MEM:
            color = best_color(name, colors, graph)
            colors[name] = color
            update_uncolored_neighbors(saturations, colors, graph, name)

        saturations[name] = -1  # remove saturations[name]

    return colors


def update_uncolored_neighbors(saturations, colors, graph, name):
    saturations.update((
        n for n in graph[name]
        if isinstance(n, ext.Name) and colors[n] is NOT_MEM
    ))


def best_color(name, colors, graph):
    color = 0
    while color in (colors[n] for n in graph[name]):
        color += 1
    return color


def interference_graph(statements):
    graph = defaultdict(set)
    # print("##########################")
    for stmt, l_after in iter_livenesses(statements):
        # print("{:40.40}".format(str(stmt)), l_after)
        if isinstance(stmt, C.INSTANTIATING_INSTRUCTIONS):
            add_interferences(
                graph, stmt.written_args(), l_after - set(stmt.args)
            )
        elif isinstance(stmt, x86.Call):
            add_interferences(graph, C.CSAVE_REGS, l_after)
        elif isinstance(stmt, C.MODIFYING_INSTRUCTIONS):
            wargs = stmt.written_args()
            add_interferences(graph, wargs, l_after - wargs)
    # print("############################")
    return graph


def iter_livenesses(statements, l_after=None):
    l_after = l_after or set()
    for stmt in reversed(statements):
        yield stmt, l_after
        # Calculate the previous l_after
        # L_after(k - 1) = (L_after(k) - W(k)) U R(k)
        if isinstance(stmt, x86.If):
            for st, la_body in iter_livenesses(stmt.body, set(l_after)):
                yield st, la_body
            for st, la_orelse in iter_livenesses(stmt.orelse, set(l_after)):
                yield st, la_orelse
            l_after = la_body | la_orelse
            if isinstance(stmt.test, ext.Name):
                l_after.add(stmt.test)
        elif isinstance(stmt, x86.While):
            # print("====")
            # print(l_after)
            for st, l_after in while_livenesses(stmt, l_after):
                # print(st, l_after)
                yield st, l_after
            liveness_step_before(l_after, st)
            # print("====")
        else:
            liveness_step_before(l_after, stmt)


def while_livenesses(whl, l_after):

    # Consider the program points:
    # > l_before
    # whl.tasm
    # > l_middle
    # while (whl.test) {...}
    # > l_after

    # l_middle is the last liveness of while_live_helper(whl, l_after)

    # print("::::::::::::::::::")
    for stmt, l_after in while_live_helper(whl, l_after):
        # if isinstance(stmt, x86.While):
        #     print("{:.40}".format(str(stmt)), l_after)
        yield stmt, l_after
    for stmt, l_after in iter_livenesses(whl.tasm, l_after):
        # print("{:.40}".format(str(stmt)), l_after)
        yield stmt, l_after
    # print("::::::::::::::::::")


def while_live_helper(whl, l_after):

    # Consider the program points
    # > L0
    # while (whl.test) {
    # > L1
    #   whl.body
    # > L2
    #   whl.tasm
    # > L3
    # }
    # > l_after

    # Note that:
    # L0 = liveness_before(whl.test, L1 | l_after)
    # L1 = liveness_before(whl.body, L2)
    # L2 = liveness_before(whl.tasm, L3)
    # L3 = L0

    l0 = set(l_after) | set(
        [whl.test] if isinstance(whl.test, ext.Name) else []
    )
    l3 = l0

    l_test = [(s, set(li)) for s, li in iter_livenesses(whl.tasm, l3)]
    l2 = set(l_test[-1][1])
    liveness_step_before(l2, l_test[-1][0])

    l_body = [(s, set(li)) for s, li in iter_livenesses(whl.body, l2)]
    l1 = set(l_body[-1][1])
    liveness_step_before(l1, l_body[-1][0])

    l_after_new = l_after | l1
    diff = l_after_new - l_after

    return (while_live_helper(whl, l_after_new) if diff else (l_test + l_body))


def liveness_step_before(l_after, inst):
    l_after -= inst.written_args()
    l_after |= inst.read_args()


def add_interferences(graph, wargs, interfering):
    for node in wargs:
        graph[node] |= interfering
        for n in interfering:
            graph[n].add(node)


def _new_unspillable():
    _new_unspillable.ctr += 1
    # alcu - alloc unspillable
    return ext.Name('#alcu{}'.format(_new_unspillable.ctr), max_color=C.N_REGS)


_new_unspillable.ctr = 0
