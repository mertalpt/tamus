import copy
import random
import tempfile
from typing import Optional

from . import pyuppaal, ta_helper


def add_path(template, path_source, path_target, n, li, clocks, lower_bounds, upper_bounds, final_guard):
    """ Add n locations from path_source to path_target starting from li (integer).
        Add n+1 transitions to form a path.
        Given a set of clocks, a period and a threshold for each clock add resets and guards such that:
                In particular, bounds is a list of tuples of the form clock index ind - period p - bound b:
                clocks[ind] is reset and checked in every p-th transition with threshold b (upper or lower)
    """
    source = template.get_location_by_name(path_source)
    # Transition leaving l_0
    target_name = 'l' + str(li)
    target = pyuppaal.Location(name=target_name)
    template.locations += [target]
    # Reset each clock except the last one on transitions leaving l_0
    reset_str = ' , '.join([clocks[i] + " = 0 " for i in range(len(clocks))])
    template.transitions += [pyuppaal.Transition(source=source, target=target,
                                                 guard='', assignment=reset_str)]
    source = template.get_location_by_name(target_name)
    for i in range(1, n + 1):
        id = i + li
        target_name = 'l' + str(id)
        if i == n:  # the target is path_target, no need to add
            target_name = path_target
            target = template.get_location_by_name(target_name)
        else:
            target = pyuppaal.Location(name=target_name)
            template.locations += [target]
        # the indices of clocks that will be checked and reset on source to target
        clock_ind_lower = []
        clock_ind_upper = []

        for j in range(len(lower_bounds)):
            if i % lower_bounds[j][1] == 0:
                clock_ind_lower += [j]
        for j in range(len(upper_bounds)):
            if i % upper_bounds[j][1] == 0:
                clock_ind_upper += [j]

        guard_str_lower = ' && '.join(
            [clocks[lower_bounds[j][0]] + " >= " + str(lower_bounds[j][2]) for j in clock_ind_lower])
        guard_str_upper = ' && '.join(
            [clocks[upper_bounds[j][0]] + " <= " + str(upper_bounds[j][2]) for j in clock_ind_upper])

        if guard_str_lower and guard_str_upper:
            guard_str = guard_str_lower + ' && ' + guard_str_upper
        elif guard_str_upper:
            guard_str = guard_str_upper
        elif guard_str_lower:
            guard_str = guard_str_lower
        else:
            guard_str = ''
        if i == n:
            guard_str = final_guard if not guard_str else final_guard + " && " + guard_str
        reset_indices = [lower_bounds[j][0] for j in clock_ind_lower] + \
                        [upper_bounds[j][0] for j in clock_ind_upper]
        reset_str = ' , '.join([clocks[i] + " = 0 " for i in reset_indices])

        template.transitions += [pyuppaal.Transition(source=source, target=target,
                                                     guard=guard_str, assignment=reset_str)]
        source = template.get_location_by_name(target_name)

    return template


def generator(clocks, lower_bounds, upper_bounds, final_guard, path_length, folder_path, ex_name):
    template = pyuppaal.Template("TA")
    template.locations += [pyuppaal.Location(name='l0')]
    template.initlocation = template.locations[0]
    template.locations += [pyuppaal.Location(name='l1')]
    nta = pyuppaal.NTA(templates=[template])

    nta.declaration = "clock " + ", ".join(clocks) + ";"
    nta.system = "\nta = TA();\n system ta;"

    start_index = 2
    # Add paths
    for i in range(len(lower_bounds)):
        add_path(template, 'l0', 'l1', path_length, start_index, clocks[0:-1],
                 lower_bounds[i], upper_bounds[i], final_guard)
        start_index += path_length

    # Store the model
    template.layout()
    xml_string = nta.to_xml()

    ta_file_path = folder_path + ex_name + ".xml"
    ta_file = open(ta_file_path, 'w')
    ta_file.write(xml_string)
    ta_file.close()
    query_file_path = folder_path + ex_name + ".q"
    with open(query_file_path, "w") as query_file:
        query_file.write("E<> ta.l1")


def benchmark_generation_helper(ci, cc, t, lp, kl, ku):
    """ci lowest clock index, cc is clock count, t is used to determine thresholds,
    lp is the lowest period, the other periods are computed w.r.to lp,
    kl and ku are used in threshold computation."""

    # half of it is used for lower bounds, half of it is used for upper bounds.
    cch = cc // 2
    lower_bounds = []
    upper_bounds = []

    for i in range(cch):
        # Set the lower bound
        lbp = (i + 1) * lp
        ubp = lbp + 1
        lower_bounds.append((i + ci, lbp, (i + 1) * t + kl))
        upper_bounds.append((i + ci + cch, ubp, ubp * (t / lp) - ku))

    return lower_bounds, upper_bounds


def generate_benchmarks(folder):
    t = 10
    lp = 2
    kl = 1
    clocks = ['x0', 'x1', 'x2']
    ci = 3  # the index of the clock to be added next, always odd.
    cc = 2

    file_names = []
    # BENCHMARKS
    while ci < 8:
        for path_length in [6, 12, 18, 24, 30]:
            lower_bounds = []
            upper_bounds = []

            final_constraint = 'x' + \
                               str(cc) + " <= " + str(t * (path_length + 1))
            # First path
            lb, ub = benchmark_generation_helper(0, cc, t, lp, kl, 0)
            lower_bounds.append(lb)
            upper_bounds.append(ub)
            ex_name = 'test' + str(len(clocks)) + '_' + \
                      str(path_length) + '_' + str(len(lower_bounds))
            print(ex_name, lower_bounds, upper_bounds)
            generator(clocks, lower_bounds, upper_bounds,
                      final_constraint, path_length, folder, ex_name)
            file_names.append(ex_name)
            # Second path
            lb, ub = benchmark_generation_helper(0, cc, 16, lp + 2, kl, 0)
            lower_bounds.append(lb)
            upper_bounds.append(ub)
            ex_name = 'test' + str(len(clocks)) + '_' + \
                      str(path_length) + '_' + str(len(lower_bounds))
            print(ex_name, lower_bounds, upper_bounds)
            final_constraint = 'x' + \
                               str(cc) + " <= " + str(4 * (path_length - 2) - 2)
            generator(clocks, lower_bounds, upper_bounds,
                      final_constraint, path_length, folder, ex_name)
            file_names.append(ex_name)
        # Add two more clocks:
        clocks.append('x' + str(ci))
        clocks.append('x' + str(ci + 1))
        ci += 2
        cc += 2
    return file_names


def generate_nonvacuity_benchmarks(
        out_dir_path,
        model_template_file=None,
        nexamples=1,
        nclock=2,
        nautomata=4,
        nlocation=6,
        ntransition=9,
        threshold_min=5,
        threshold_max=20,
        mutation_count=None,
        enforce_vacuity=False,
        max_considered_example_count=None,
):
    def random_template_generator(name: str, nlocation: int, ntransition: int) -> pyuppaal.Template:
        """
        Generates a random template with the given parameters.
        Some constraints:
        - Making locations reachable is prioritized when creating new transitions.
        - Multiple transitions between locations in either direction is possible.
        - The template is empty except for the locations and the transitions.

        :param name: Name to be given to the template.
        :param nlocation: Number of locations in the template.
        :param ntransition: Total number of transitions between the locations.
        :return: pyuppaal.Template object filled with the randomly generated template.
        """
        assert nlocation >= 3, \
            'Generator assumes there must exist at least a start, an accept and an error state in a TA.'

        locations: list[pyuppaal.Location] = [pyuppaal.Location(id=f'id{n}', name=f'l{n}') for n in range(nlocation)]
        initlocation: pyuppaal.Location = locations[0]
        transitions: list[pyuppaal.Transition] = []

        reachable: set[pyuppaal.Location] = {initlocation}
        unreachable: set[pyuppaal.Location] = set(locations[1:])

        for _ in range(ntransition):
            # Location in index 2 is the error state that should be absorbing
            source_candidates = reachable - {locations[2]}
            if unreachable:
                source = random.sample(source_candidates, 1)[0]
                target = random.sample(unreachable, 1)[0]
                unreachable.remove(target)
                reachable.add(target)
            else:
                source = random.sample(source_candidates, 1)[0]
                target = random.sample(reachable, 1)[0]
            transition = pyuppaal.Transition(source, target)
            transitions.append(transition)

        template: pyuppaal.Template = pyuppaal.Template(
            name, locations=locations, initlocation=initlocation, transitions=transitions
        )
        return template

    def random_nta_generator(
            nclock: int,
            nautomata: int,
            nlocation: int,
            ntransition: int
    ) -> tuple[pyuppaal.NTA, list[str]]:
        """
        Randomly generates a system of automata without constraints on the locations or the transitions.
        :param nclock: Number of clocks in the system.
        :param nautomata: Number of automata in the system.
        :param nlocation: Number of locations per automaton.
        :param ntransition: Number of transitions per automaton.
        :return: A randomly generated pyuppaal.NTA object.
        """
        clocks: list[str] = [f'c{i}' for i in range(nclock)]
        automata: list[pyuppaal.Template] = [
            random_template_generator(f'Automaton{n}', nlocation, ntransition) for n in range(nautomata)
        ]
        system_init: list[str] = []
        system: list[str] = []
        for idx, automaton in enumerate(automata):
            system_init.append(f'template{idx} = {automaton.name}();')
            system.append(f'template{idx}')
        nta: pyuppaal.NTA = pyuppaal.NTA(
            declaration=f'clock {", ".join(clocks)};' + '\n',
            system='\n'.join(system_init) + '\n' + f'system {", ".join(system)};',
            templates=automata
        )
        queries: list[str] = []
        for i, automaton in enumerate(automata):
            query = [f'template{i}.{automaton.locations[1].name}']
            for j, automaton in enumerate(automata):
                if i == j:
                    continue
                query.extend(['&&', f'!template{j}.{automaton.locations[2].name}'])
            query = ' '.join(query)
            query = f'E<> ({query})'
            queries.append(query)
        return nta, queries

    def constraint_generator(
            nta: pyuppaal.NTA,
            nclock: int,
            threshold_min: int,
            threshold_max: int,
            mutation_count: Optional[int],
    ) -> pyuppaal.NTA:
        """
        Fills transitions of the given nta with randomly generated constraints.

        Note that clocks are implicitly generated in the 'c{i}' format with i in 0 to number of clocks-1.

        :param nta: A pyuppaal.NTA object.
        :param nclock: Number of clocks in the NTA object.
        :param threshold_min: Minimum value for the constraint constant.
        :param threshold_max: Maximum value for the constraint constant.
        :return: A copy of the given NTA object with constraints filled in.
        """
        nta_copy: pyuppaal.NTA = copy.deepcopy(nta)
        operators = ['<', '>', '==', '<=', '>=']
        if mutation_count is None:
            mutation_limits = [0] * len(nta_copy.templates)  # Will not be really used
        else:
            # Spread mutation count over the templates
            mutation_limits = [mutation_count // len(nta_copy.templates)] * len(nta_copy.templates)
            # Spread the remainder over the earlier templates
            for i in range(mutation_count % len(nta_copy.templates)):
                mutation_limits[i] += 1
        for template_idx, template in enumerate(nta_copy.templates):
            clocks = [f'c{i}' for i in range(nclock)]
            # Iterate over template transitions in a random order
            for transition in random.sample(template.transitions, len(template.transitions)):
                # Cut off mutations if a limit is specified
                if mutation_count is not None and mutation_limits[template_idx] <= 0:
                    break
                else:
                    mutation_limits[template_idx] -= 1
                clock_count = random.randint(1, len(clocks))
                used_clocks = random.sample(clocks, clock_count)
                used_operators = random.choices(operators, k=clock_count)
                used_thresholds = [random.randint(threshold_min, threshold_max) for _ in range(clock_count)]
                guard_string = ' && '.join(
                    [f'{used_clocks[i]}{used_operators[i]}{used_thresholds[i]}' for i in range(clock_count)]
                )
                reset_count = random.randint(0, len(clocks))
                reset_clocks = random.sample(clocks, reset_count)
                reset_string = ', '.join([f'{clock}=0' for clock in reset_clocks])
                transition.guard.value = guard_string
                transition.assignment.value = reset_string
            template.layout()
        return nta_copy

    if model_template_file is None:
        nta, queries = random_nta_generator(nclock, nautomata, nlocation, ntransition)
    else:
        nta, queries = pyuppaal.NTA.from_xml(model_template_file), None
    # Generate examples
    valid_example_count = 0
    total_example_count = 0
    while valid_example_count < nexamples:
        if total_example_count % 25 == 0:
            print(
                f'Running: Considered {total_example_count} examples and found {valid_example_count} vacuous examples.'
            )
        if max_considered_example_count is not None and total_example_count >= max_considered_example_count:
            break
        total_example_count += 1
        nta_copy = constraint_generator(nta, nclock, threshold_min, threshold_max, mutation_count)
        base_file_path = f'{out_dir_path}/Example-{valid_example_count}'
        ta_file_path = f'{base_file_path}.xml'
        ta_file_contents = nta_copy.to_xml()

        # Ensure that the generated model is vacuous
        if enforce_vacuity and queries is not None:
            # Generate temporary files for UPPAAL verification
            skip_model = False
            with tempfile.TemporaryDirectory() as tempdir:
                with open(f'{tempdir}/tmp-model.xml', mode='w+') as tmp_model:
                    tmp_model.write(ta_file_contents)
                    tmp_model.flush()
                    for query in queries:
                        with open(f'{tempdir}/tmp-query.q', mode='w+') as tmp_query:
                            tmp_query.write(query)
                            tmp_query.flush()
                            stdoutdata, traces = ta_helper.verifyWithTrace(tmp_model.name, tmp_query.name, 'All')
                            # Query did pass, model is not vacuous
                            if traces:
                                skip_model = True
                                break
                    if skip_model:
                        continue

        valid_example_count += 1
        with open(ta_file_path, mode='w') as f:
            f.write(ta_file_contents)
            print(f'Found valid example, writing to: {ta_file_path}')
        if queries is not None:
            query_file_path = f'{base_file_path}.q'
            query_file_contents = '\n'.join(queries) + '\n'
            with open(query_file_path, 'w') as f:
                f.write(query_file_contents)

    print(f'Final: Considered {total_example_count} examples and found {valid_example_count} vacuous examples.')
