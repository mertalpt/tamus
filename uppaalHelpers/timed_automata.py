import copy
import networkx as nx

#  import matplotlib.pyplot as plt


class TimedAutomata:

    def __init__(self):
        """Empty TA constructor."""
        self.g = nx.MultiDiGraph()
        self.initial_location = None

        self.constraint_registry = dict()  # constraint_id: constraint, source-target/or location, quard
        self.parsed_invariants = dict()  # location : parsed invariant ( a list)
        self.parsed_guards = dict()  # source-target : parsed guard (a list)
        self.resets = dict()  # source-target : list of clocks to be reset
        self.clocks = []
        self.templates = None
        self.next_id = 0

    def initialize_from_template(self, template):
        """Initialize TA from pyuppaal template."""
        self.templates = [template]
        self.initial_location = template.initlocation.name.value
        # Add each location as a node:
        for l in template.locations:
            self.g.add_node((template.name, l.name.value), invariant=l.invariant.value)
            # Add invariants to the registry.
            self._register_location_constraints(l, template.name)

        # Add each transition as an edge:
        for t in template.transitions:
            self.g.add_edge((template.name, t.source.name.value), (template.name, t.target.name.value),
                            key=(t.guard.value, t.assignment.value, t.synchronisation.value))
            # Add the guards to the registry.
            self._register_transition_constraints(t, template.name)
            # If there are multiple edges between two locations, analysis is only possible if these edges have different
            # synchronisations or one edge does not have a synchronisation and others have different synchronisations.
            self._parse_reset(t, template.name)

        self.clocks = sorted(self.clocks)

        # For debugging
        # print (self.constraint_registry)
        # print(self.parsed_invariants)
        # print(self.parsed_guards)

    """ def plot(self):
        plt.subplot()
        nx.draw(self.g, with_labels=True, font_weight='bold')
        plt.show()
    """
    def initialize_from_templates(self, templates):
        """Initialize TA from pyuppaal template."""
        self.templates = templates
        # Add each location as a node:
        for template in templates:
            for l in template.locations:
                # Add invariants to the registry.
                self._register_location_constraints(l, template.name)

            # Add each transition as an edge:
            for t in template.transitions:
                # Add the guards to the registry.
                self._register_transition_constraints(t, template.name)
                # If there are multiple transitions between two locations,
                # analysis is only possible if these transitions have different synchronisations or
                # one transition does not have a synchronisation and others have different synchronisations.
                self._parse_reset(t, template.name)

        self.clocks = sorted(self.clocks)

    def initialize_path_TA_from_template(self, template, clist):
        """Initialize TA from pyuppaal template."""
        self.template = template
        # Prune the template so that it only contains transitions and locations from clist.
        # First find the indices of locations from clist:
        index_set = [i for i in range(len(self.template.locations))
                     if self.template.locations[i].name.value in clist]
        self.template.locations = [self.template.locations[i] for i in index_set]

        index_set = [i for i in range(len(self.template.transitions))
                     if self.template.transitions[i].source.name.value in clist and
                        self.template.transitions[i].target.name.value in clist]
        self.template.transitions = [self.template.transitions[i] for i in index_set]
        self.initialize_from_template(self.template)

    def _register_transition_constraints(self, t, template_name):
        """Register constraints. This will be only called from initialization function."""
        if not t.guard.value:
            self.parsed_guards[(template_name, t.source.name.value, t.target.name.value, t.synchronisation.value)] = []
            return
        c_list = t.guard.value.split('&&')
        for c in c_list:
            if ('==' in c) or ('!=' in c) or ('true' in c):
                continue
            self.constraint_registry['c' + str(self.next_id)] = \
                [c, (template_name,
                     t.source.name.value,
                     t.target.name.value,
                     t.synchronisation.value)]
            self.next_id += 1
            self.parse_add_clock(c)
        self.parsed_guards[(template_name,
                            t.source.name.value,
                            t.target.name.value,
                            t.synchronisation.value)] = [
            self.parse_inequality_simple(c) for c in c_list]

    def _register_location_constraints(self, l, template_name):
        """Register constraints. This will be only called from initialization function."""
        if not l.invariant.value:
            self.parsed_invariants[(template_name, l.name.value)] = []
            return
        c_list = l.invariant.value.split('&&')
        for c in c_list:
            if ('==' in c) or ('true' in c):
                continue
            self.constraint_registry['c' + str(self.next_id)] = \
                [c, (template_name, l.name.value)]
            self.next_id += 1
            self.parse_add_clock(c)
        # Parse each constraint from c_list:
        self.parsed_invariants[(template_name, l.name.value)] = [self.parse_inequality_simple(c) for c in c_list]

    def constraint_keys_for_ta(self):
        """Generates the list of simple constraints of TA"""
        return self.constraint_registry.keys()

    def constraint_lists_for_all_paths(self, final_location):
        """Generates a list of lists, each list corresponds to the set of constraints encountered in
        a path from initial location to the given final location."""
        paths = nx.all_simple_paths(self.g, self.initial_location, final_location)
        constraints = []
        paths_processed = []
        # Get the path as the list of locations
        for path in map(nx.utils.pairwise, paths):
            constraints.append([])
            paths_processed.append([self.initial_location])
            for l_pair in path:
                # Invariant
                constraints[-1] = constraints[-1] + self._get_constraints_on_transition(l_pair[0])
                # Guard
                constraints[-1] = constraints[-1] + self._get_constraints_on_transition(l_pair)
                # Location to path
                paths_processed[-1].append(l_pair[1])
        return constraints, paths_processed

    def _get_constraints_on_transition(self, pair):
        ids = []
        for key in self.constraint_registry:
            value = self.constraint_registry[key]
            if value[1] == pair:
                ids.append(key)
        return ids

    def generate_relaxed_templates(self, relax_set):
        """Removes the constraints from the relaxed set and returns the resulting template."""

        transition_relax_set = {}
        location_relax_set = {}
        for cid in relax_set:
            constraint, l_t = self.constraint_registry[cid]
            if len(l_t) == 4:  # A constraint along a transition.
                transition_relax_set.setdefault(l_t, []).append(constraint)  # Insert or append
            else:
                location_relax_set.setdefault(l_t, []).append(constraint)

        new_templates = []
        for template in self.templates:
            new_templates.append(copy.deepcopy(template))  # The relax operation will be performed on the new template.
        # Go through the transitions, relax them according to transition_relax_set.
        for new_template in new_templates:
            for t in new_template.transitions:
                t_relax_set = transition_relax_set.get((new_template.name,
                                                        t.source.name.value,
                                                        t.target.name.value,
                                                        t.synchronisation.value), [])
                if t_relax_set:
                    t.guard.value = self._relax_constraint(t.guard.value, t_relax_set)

            # Go through the locations, relax invariants according to the location_relax_set.
            for l in new_template.locations:
                l_relax_set = location_relax_set.get((new_template.name, l.name.value), [])
                if l_relax_set:
                    l.invariant.value = self._relax_constraint(l.invariant.value, l_relax_set)

        return new_templates

    def _relax_constraint(self, constraint, relax_set):
        """Returns a string by removing each constraint from the relax set. """
        constraint_list = constraint.split('&&')
        c_dif = [c for c in constraint_list if c not in relax_set]  # InlinesSet difference for two lists.
        return '&&'.join(c_dif)

    def print_registry(self, file_name):
        f = open(file_name, "w")
        for k in sorted(self.constraint_registry.keys()):
            f.write(str(k) + " : " + str(self.constraint_registry[k]) + "\n")
        f.close()

    def parse_inequality_simple(self, inequality):
        ind = 0
        for i in range(len(inequality)):
            if inequality[i] in ['<', '>', '=']:
                ind = i
                break
        clock_name = inequality[0:ind].strip()
        operator = inequality[ind]
        equality = False
        if inequality[ind+1] == '=':
            ind += 1
            equality = True
        rest = inequality[ind+1:].strip()
        threshold = int(rest)

        return clock_name, operator, threshold, equality

    def _parse_reset(self, t, template_name):
        r_list = t.assignment.value.split(',')
        self.resets[(template_name, t.source.name.value, t.target.name.value, t.synchronisation.value)] = []
        for r in r_list:
            if len(r) != 0:
                clock_name = self.parse_add_clock(r)
                self.resets[(template_name,
                             t.source.name.value,
                             t.target.name.value,
                             t.synchronisation.value)].append(clock_name)

    def parse_add_clock(self, inequality):
        """Input is an inequality x < 10 or x >= p1, add x to the set of clocks."""
        ind = 0
        for i in range(len(inequality)):
            if inequality[i] in ['>', '<', '=']:
                ind = i
                break
        clock_name = inequality[0:ind].strip()
        if clock_name not in self.clocks:
            self.clocks.append(clock_name)
        return clock_name

    def parametrize_msr(self, msr):
        constraint_to_parameter = dict()
        for i in range(len(msr)):
            c = self.constraint_registry[msr[i]]
            parsed_inequality = self.parse_inequality_simple(c[0])
            constraint_to_parameter[(c[1], parsed_inequality)] = i
        return constraint_to_parameter

    def _parametrize_constraint(self, constraint, parametrize_set, parameter_values_set):
        """Returns a s string by adding parameter to each constraint"""
        constraint_list = constraint.split('&&')
        c_par = []
        for c in constraint_list:
            if c in parametrize_set:
                if "<" in c:
                    c_par.append(c + "+par" + str(parameter_values_set[parametrize_set.index(c)]))
                elif ">" in c:
                    c_par.append(c + "-par" + str(parameter_values_set[parametrize_set.index(c)]))
            else:
                c_par.append(c)
        return '&&'.join(c_par)

    def generate_relaxed_and_parametrized_templates(self, relax_set, parametrize_set):
        """Removes the constraints from the relaxed set and returns the resulting template."""

        transition_relax_set = {}
        location_relax_set = {}
        for cid in relax_set:
            constraint, l_t = self.constraint_registry[cid]
            if len(l_t) == 4:  # A constraint along a transition.
                transition_relax_set.setdefault(l_t, []).append(constraint)  # Insert or append
            else:
                location_relax_set.setdefault(l_t, []).append(constraint)

        parameter_count = 0
        transition_par_set = {}
        location_par_set = {}
        transition_par_values = {}
        location_par_values = {}
        for cid in parametrize_set:
            constraint, l_t = self.constraint_registry[cid]
            if len(l_t) == 4:  # A constraint along a transition.
                transition_par_set.setdefault(l_t, []).append(constraint)  # Insert or append
                transition_par_values.setdefault(l_t, []).append(parameter_count)
                parameter_count += 1
            else:
                location_par_set.setdefault(l_t, []).append(constraint)
                location_par_values.setdefault(l_t, []).append(parameter_count)
                parameter_count += 1

        new_templates = []
        for template in self.templates:
            new_templates.append(copy.deepcopy(template))  # The relax operation will be performed on the new template.
        # Go through the transitions, relax them according to transition_relax_set.
        for new_template in new_templates:
            for t in new_template.transitions:
                t_relax_set = transition_relax_set.get((new_template.name,
                                                        t.source.name.value,
                                                        t.target.name.value,
                                                        t.synchronisation.value), [])
                if t_relax_set:
                    t.guard.value = self._relax_constraint(t.guard.value, t_relax_set)

                t_par_set = transition_par_set.get((new_template.name,
                                                    t.source.name.value,
                                                    t.target.name.value,
                                                    t.synchronisation.value), [])
                t_par_values = transition_par_values.get((new_template.name,
                                                          t.source.name.value,
                                                          t.target.name.value,
                                                          t.synchronisation.value), [])
                if t_par_set:
                    t.guard.value = self._parametrize_constraint(t.guard.value, t_par_set, t_par_values)

            # Go through the locations, relax invariants according to the location_relax_set.
            for l in new_template.locations:
                l_relax_set = location_relax_set.get((new_template.name, l.name.value), [])
                if l_relax_set:
                    l.invariant.value = self._relax_constraint(l.invariant.value, l_relax_set)

                l_par_set = location_par_set.get((new_template.name, l.name.value), [])
                l_par_values = location_par_values.get((new_template.name, l.name.value), [])
                if l_par_set:
                    l.invariant.value = self._parametrize_constraint(l.invariant.value, l_par_set, l_par_values)

        return new_templates, parameter_count
