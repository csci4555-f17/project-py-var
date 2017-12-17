
import x86ir as x86


def remove_ctrl_flow(stmts):

    new_stmts = []
    for s in stmts:

        if isinstance(s, (x86.If, x86.While)):
            rem_func = remove_if if isinstance(s, x86.If) else remove_while
            new_stmts.extend(rem_func(s))
        else:
            new_stmts.append(s)

    return new_stmts


def remove_if(s):
    lbl_else, lbl_end = _free_if_labels()

    stmts = [
        x86.Cmp("$0", s.test),
        x86.Je(lbl_else)
    ]

    stmts += remove_ctrl_flow(s.body)
    stmts += [
        x86.Jmp(lbl_end),
        x86.Label(lbl_else)
    ]
    stmts += remove_ctrl_flow(s.orelse)
    stmts.append(x86.Label(lbl_end))

    return stmts


def remove_while(s):
    lbl_start, lbl_end = _free_while_labels()
    return (
        [x86.Label(lbl_start)]
        + remove_ctrl_flow(s.tasm)
        + [x86.Cmp("$0", s.test), x86.Je(lbl_end)]
        + remove_ctrl_flow(s.body)
        + [x86.Jmp(lbl_start), x86.Label(lbl_end)]
    )


def _free_if_labels():
    _free_if_labels.ctr += 1
    suffix = '_label_{}'.format(_free_if_labels.ctr)
    return 'else' + suffix, 'fi' + suffix


_free_if_labels.ctr = 0


def _free_while_labels():
    _free_while_labels.ctr += 1
    suffix = '_label_{}'.format(_free_while_labels.ctr)
    return 'while' + suffix, 'end' + suffix


_free_while_labels.ctr = 0
