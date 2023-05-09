import argparse
import tempfile
import time

from copy import deepcopy
from functools import reduce
from typing import Optional

from tamus import Tamus
from uppaalHelpers import pyuppaal, ta_helper


def minimum_union_combiner(
        msr_sets: list[list[set[str]]], 
        idx: int,
        union: set[str], 
        card: Optional[int] = None,
) -> tuple[set[str], int]:
    """Find the minimum union of constraints to remove by picking
    a constraint set for each automaton in the system from the
    input list of MSR sets.
    """
    if idx == len(msr_sets):
        return union, len(union)
    
    min_union, min_card = None, card
    for msr_set in msr_sets[idx]:
        tmp = union.union(msr_set)
        if min_card is not None and len(tmp) >= min_card:
            continue
        tmp_union, tmp_card = minimum_union_combiner(msr_sets, idx+1, tmp, min_card)
        if min_card is None or tmp_card < min_card:
            min_union, min_card = tmp_union, tmp_card
    
    return min_union, min_card


def combiner_optimizer(msr_sets: list[list[set[str]]]) -> tuple[list[list[set[str]]], set[str]]:
    """Extract common constraints and sorts by set size for average case optimization."""
    msr_sets = deepcopy(msr_sets)
    
    # First sort pass
    for idx in range(len(msr_sets)):
        msr_sets[idx].sort(key=lambda x: len(x))

    # Extraction pass
    extracts = []
    for curr_sets in msr_sets:
        extract = reduce(lambda x, y: x.intersection(y), curr_sets, curr_sets[0])
        extracts.append(extract)

    # Removal pass
    extract = reduce(lambda x, y: x.union(y), extracts, set())
    for idx, curr_sets in enumerate(msr_sets):
        for jdx, curr_set in enumerate(curr_sets):
            curr_sets[jdx] = curr_set.difference(extract)

    # Second sort pass
    for idx in range(len(msr_sets)):
        msr_sets[idx].sort(key=lambda x: len(x))

    return msr_sets, extract


def treewalker_repair(tamus: Tamus, queries, templates, curr_idx, solutions, base_dir='.', find_all=True):
    """Run a recursive search on the TAs and yield solutions from base cases."""
    # No more templates
    if curr_idx == len(templates):
        solutions.append(templates)
        return
    print(f'Curr Idx: {curr_idx} out of {len(templates) - 1}')
    curr_query_path = queries[curr_idx]
    # Write a temporary model file
    model_path_base = f'{base_dir}/tmp_iteration.xml'
    curr_nta = pyuppaal.NTA(tamus.model.declaration, tamus.model.system, templates)
    model_path = ta_helper.set_templates_and_save(model_path_base, curr_nta, templates)
    # We will trick Tamus into thinking we called a subtemplate with the 'amsr' task
    # We will be calling the generating function manually, so not sure how much of this is necessary
    args_var = vars(tamus.args)
    args_var['task'] = 'amsr'
    args_copy = argparse.Namespace(**args_var)
    curr_tamus = Tamus(model_path, curr_query_path, "All", args_copy)
    curr_tamus.timelimit = args_copy.msr_timelimit if args_copy.msr_timelimit != None else 1000000
    curr_tamus.verbosity = args_copy.verbose if args_copy.verbose != None else 0
    curr_tamus.task = args_copy.task
    curr_tamus.usePathAnalysis = args_copy.path_analysis
    curr_tamus.useMultiplePathCores = args_copy.multiple_path_cores
    curr_tamus.minimumMSR(False)
    msres, _, _ = curr_tamus.get_MSRes()

    # Iterate over possible relaxations
    for msr in msres:
        msr_templates = curr_tamus.TA.generate_relaxed_templates(msr)
        # Process rest of the templates
        treewalker_repair(tamus, queries, msr_templates, curr_idx + 1, solutions, base_dir)
        # Determine if we are done or if we should continue
        if not find_all and len(solutions) > 0:
            break
    
    if len(solutions) > 0:
        return
    raise Exception('Non-vacuity is impossible.')


def combiner_repair(tamus: Tamus, queries, templates, find_all=False, use_optimizer=True):
    """Run an iterative search on the TAs and yields solutions from combinations."""
    msr_sets = []
    for idx, _ in enumerate(templates):
        print(f'Curr Idx: {idx} out of {len(templates) - 1}')
        curr_query_path = queries[idx]
        # We will trick Tamus into thinking we called a subtemplate with the 'amsr' task
        # We will be calling the generating function manually, so not sure how much of this is necessary
        args_var = vars(tamus.args)
        args_var['task'] = 'amsr'
        args_copy = argparse.Namespace(**args_var)
        curr_tamus = Tamus(tamus.model_file, curr_query_path, "All", args_copy)
        curr_tamus.timelimit = args_copy.msr_timelimit if args_copy.msr_timelimit != None else 1000000
        curr_tamus.verbosity = args_copy.verbose if args_copy.verbose != None else 0
        curr_tamus.task = args_copy.task
        curr_tamus.usePathAnalysis = args_copy.path_analysis
        curr_tamus.useMultiplePathCores = args_copy.multiple_path_cores
        curr_tamus.minimumMSR(False)
        print('Getting MSRs')
        msres, _, _ = curr_tamus.get_MSRes()
        # Sometimes empty constraint lists come with MSRs, filter them
        msr_set = [set(msr) for msr in msres if len(msr) != 0]
        # If we filtered everything, it means there was no need to remove a constraint
        if len(msr_set) == 0:
            msr_set.append(set())
        msr_sets.append(msr_set)
    
    if not find_all:
        # Calculate the minimal overall reduction
        if use_optimizer:
            sets, extract = combiner_optimizer(msr_sets)
        else:
            sets, extract = msr_sets, set()
        solution, _ = minimum_union_combiner(sets, 0, set())
        solution = solution.union(extract)
        solution = list(solution)
        msres = [[solution]]
    else:
        # TODO: This is wrong, we need to take unions of combinations
        msres = [[list(msr) for msr in msr_set] for msr_set in msr_sets]

    print('Generating templates')
    candidates = []
    for idx, curr_msres in enumerate(msres):
        print(f'Curr Idx: {idx} out of {len(templates) - 1}')
        curr_query_path = queries[idx]
        # We will trick Tamus into thinking we called a subtemplate with the 'amsr' task
        # We will be calling the generating function manually, so not sure how much of this is necessary
        args_var = vars(tamus.args)
        args_var['task'] = 'amsr'
        args_copy = argparse.Namespace(**args_var)
        curr_tamus = Tamus(tamus.model_file, curr_query_path, "All", args_copy)
        curr_tamus.timelimit = args_copy.msr_timelimit if args_copy.msr_timelimit != None else 1000000
        curr_tamus.verbosity = args_copy.verbose if args_copy.verbose != None else 0
        curr_tamus.task = args_copy.task
        curr_tamus.usePathAnalysis = args_copy.path_analysis
        curr_tamus.useMultiplePathCores = args_copy.multiple_path_cores
        curr_templates = []
        print('Processing MSRs into templates')
        for msr in curr_msres:
            msr_templates = curr_tamus.TA.generate_relaxed_templates(msr)
            curr_templates.append(msr_templates)
        candidates.extend(curr_templates)
    return candidates


def repair(tamus: Tamus, find_all: bool = False, use_optimizer: bool = True, use_treewalker: bool = False):
    """
    Given N timed automata, ensure each one can reach its accepting state without making another TA go into error.

    Tamus works with single definition and query files. So, we will need a special format for them.
    There is no requirement for the definition (.xml) file.
    For the query file, there must be a query for reachability of the acceptance state of a template per line.
    Also, the lines for templates should be ordered by the order they are declared in the 'system' line in the definition.

    Example:
        In definition file, system tag is as such:
            <system>
                Template1 = TemplateA();
                Template2 = TemplateB();
                system Template1, Template2;
            </system>
        In query file, we do this:
            E<> (Template1.accept && !Template2.error)
            E<> (Template2.accept && !Template1.error)
    """
    start_time = time.process_time()
    with tempfile.TemporaryDirectory() as tempdir:
        templates = tamus.TA.templates
        queries = []
        with open(tamus.query_file) as qf:
            lines = qf.readlines()
            for idx, line in enumerate(lines):
                query_path = f'{tempdir}/query-{idx}.q'
                queries.append(query_path)
                with open(query_path, mode='w') as f:
                    f.write(line)
        if use_treewalker:
            results = []
            treewalker_repair(tamus, queries, templates, 0, results, tempdir, find_all)
        else:
            results = combiner_repair(tamus, queries, templates, find_all, use_optimizer)
        for idx, res in enumerate(results):
            res_nta = pyuppaal.NTA(tamus.model.declaration, tamus.model.system, res)
            res_model_path = ta_helper.set_templates_and_save(
                f'{tamus.model_file[:-4]}-sol-{idx}{tamus.model_file[-4:]}', res_nta, res
            )
            print(f'Found non-vacuous relaxation. Writing to "{res_model_path}"')
    end_time = time.process_time()
    print(f'Non-vacuity execution took: {end_time - start_time} seconds')
