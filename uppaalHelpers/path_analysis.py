"""Methods for checking if a path is realizable, and relaxing constraints."""
from ortools.linear_solver import pywraplp


def is_realizable(ta, path):
    """Given the template, and the path, check whether its feasible."""
    """is_realizable(ta,["l0","l1","l2","l1","l3","l4"])"""
    # Get clocks along the path.
    clocks = []
    # for the first location
    compute_clocks(path, ta, clocks)
    clocks = sorted(clocks)
    return construct_path_lp(path, clocks, ta, [])[0]


def find_parameters(ta, path, msr):
    """Given the template, the path and mcs find parameters."""
    """example:find_parameters(ta,["l0","l1","l2","l1","l3","l4"],["c18","c17"])"""
    clocks = []
    compute_clocks(path, ta, clocks)
    clocks = sorted(clocks)
    _, delays, parameters = construct_path_lp(path, clocks, ta, msr)
    return delays, parameters


def compute_clocks(path, ta, clocks):
    # c : clock_name, operator, threshold, equality
    for c in ta.parsed_invariants[path[0]]:
        compute_clocks_helper(c, clocks)
    # along the path
    for i in range(1, len(path)):
        for c in ta.parsed_invariants[path[i]]:
            compute_clocks_helper(c, clocks)
        for c in ta.parsed_guards[(path[i-1], path[i])]:
            compute_clocks_helper(c, clocks)
        for x in ta.resets[(path[i-1], path[i])]:
            if x not in clocks:
                clocks.append(x)


def compute_clocks_helper(c, clocks):
    if c[0] not in clocks:
        clocks.append(c[0])


def construct_path_lp(path, clocks, ta, msr):

    number_of_variables = len(path) - 1 + len(msr)
    # assign parameters to constraints in mcs
    constraint_to_parameter = ta.parametrize_msr(msr)

    A = []  # A and B matrices for the optimization
    B = []
    clock_to_delay = dict()  # A mapping from clocks to the delay variables,
    # the dictionary will be updated as we progress along the path.
    for x in clocks:
        clock_to_delay[x] = [0]  # set all of them to delay 0 initially.

    for i in range(len(path)-1):
        # Add constraints for the invariant.
        # Leaving path[i]
        for c in ta.parsed_invariants[path[i]]:
            if constraint_to_parameter.get((path[i], c)) is not None:
                a, b = compute_constraint(clock_to_delay, c, number_of_variables,
                                          constraint_to_parameter[(path[i], c)]+len(path)-1)
            else:
                a, b = compute_constraint(clock_to_delay, c, number_of_variables, -1)
            for k in range(len(a)):
                A.append(a[k])
                B.append(b[k])

        # Add constraints for the guards.
        for c in ta.parsed_guards[(path[i], path[i+1])]:
            if constraint_to_parameter.get(((path[i], path[i+1]), c)) is not None:
                a, b = compute_constraint(clock_to_delay, c, number_of_variables,
                                          constraint_to_parameter[((path[i], path[i+1]), c)]+len(path)-1)
            else:
                a, b = compute_constraint(clock_to_delay, c, number_of_variables, -1)
            for k in range(len(a)):
                A.append(a[k])
                B.append(b[k])

        # Apply reset:
        for x in ta.resets[(path[i], path[i+1])]:
            clock_to_delay[x] = []  # Reset

        # Add constraints for the invariant.
        # Entering path[i+1]:
        for c in ta.parsed_invariants[path[i+1]]:
            if constraint_to_parameter.get((path[i], c)) is not None:
                a, b = compute_constraint(clock_to_delay, c, number_of_variables,
                                          constraint_to_parameter[(path[i+1], c)]+len(path)-1)
            else:
                a, b = compute_constraint(clock_to_delay, c, number_of_variables, -1)
            for k in range(len(a)):
                A.append(a[k])
                B.append(b[k])

        # Add delay variable to all clocks
        for x in clocks:
            clock_to_delay[x].append(i+1)

    # Set the cost:
    c = [0 for _ in range(len(path)-1)] + [1 for _ in range(len(msr))]
    # Construct solver
    solver = pywraplp.Solver('', pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)
    # Create variables for solver
    x = {}
    for j in range(len(path)-1):
        x[j] = solver.NumVar(0, solver.infinity(), 'x[' + str(j) + ']')
    for j in range(len(path)-1, len(path)-1+len(msr)):
        x[j] = solver.IntVar(0, solver.infinity(), 'x[' + str(j) + ']')

    obj_expr = [c[j] * x[j] for j in range(number_of_variables)]
    solver.Minimize(solver.Sum(obj_expr))

    for i in range(len(A)):
        constraint = solver.RowConstraint(-solver.infinity(), B[i], '')
        for j in range(number_of_variables):
            constraint.SetCoefficient(x[j], A[i][j])

    status = solver.Solve()


    delays = []
    parameters = []
    if status == solver.OPTIMAL:
        for i in range(len(path)-1):
            delays.append(x[i].solution_value())
        for i in range(len(path)-1, len(path)-1+len(msr)):
            parameters.append(x[i].solution_value())
        return True, delays, parameters
    else:
        return False, delays, parameters


def compute_constraint(clock_to_delay, c, number_of_variables, parameter):
    # c : clock_name, operator, threshold, equality
    A_row = [[0 for _ in range(number_of_variables)]]  # initialize the row
    for di in clock_to_delay[c[0]]:  # Clock to delay mapping for A
        A_row[0][di] = 1

    B_row = [c[2]]
    if c[1] == '>':  # multiply by -1
        A_row[0] = [x * -1 for x in A_row[0]]
        B_row[0] = -1 * B_row[0]

    if parameter != -1:
        A_row[0][parameter] = -1

    if c[1] == '=':  # >= && <= is equal to ==
        A_row.append([x * -1 for x in A_row[0]])
        B_row.append(-1 * B_row[0])

    return A_row, B_row
