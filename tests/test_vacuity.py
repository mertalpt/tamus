import argparse
from pathlib import Path
import tempfile
import unittest

import vacuity
from tamus import Tamus


THIS_DIR = Path(__file__).parent
TEST_ARGS = argparse.Namespace(**{
    "verbose": None,
    "msr_timelimit": None,
    "task": "nvac",
    "run_imitator_on_msr": False,
    "run_imitator_on_every_mmsr": False,
    "run_imitator_on_partition": False,
    "run_imitator_on_mg": False,
    "path_analysis": False,
    "multiple_path_cores": False,
})


class TestMinimumUnionCombiner(unittest.TestCase):

    def test_completely_empty(self):
        msr_sets = []
        min_union, _ = vacuity.minimum_union_combiner(msr_sets, 0, set())
        assert min_union == set(), \
            "Minimum union of no sets should be an empty set."
        
    def test_partly_empty(self):
        msr_sets = [[set()], [set()]]
        min_union, _ = vacuity.minimum_union_combiner(msr_sets, 0, set())
        assert min_union == set(), \
            "Minimum union of MSRs with no constraints to remove should be an empty set."

    def test_basic(self):
        msr_sets = [[{"1", "2"}]]
        min_union, _ = vacuity.minimum_union_combiner(msr_sets, 0, set())
        assert min_union == {"1", "2"}, \
            "Minimum union of a single set is the set itself."
        
    def test_multi_msr_basic(self):
        msr_sets = [[{"1", "2"}], [{"3"}]]
        min_union, _ = vacuity.minimum_union_combiner(msr_sets, 0, set())
        assert min_union == {"1", "2", "3"}, \
            "Minimum union of disjoint sets is the union of the sets."
        
    def test_multi_msr_intersecting(self):
        msr_sets = [[{"1", "2"}], [{"2", "3"}]]
        min_union, _ = vacuity.minimum_union_combiner(msr_sets, 0, set())
        assert min_union == {"1", "2", "3"}, \
            "Minimum union of two sets is the union of the sets."
        
    def test_multi_msr_competing_options(self):
        msr_sets = [[{"1", "2", "3"}], [{"2", "3", "4"}, {"4", "5"}]]
        min_union, _ = vacuity.minimum_union_combiner(msr_sets, 0, set())
        assert min_union == {"1", "2", "3", "4"}, \
            "Minimum union of sets should actually look at the result size."


class TestCombinerOptimizer(unittest.TestCase):
    
    def test_totally_empty(self):
        msr_sets = []
        sets, extract = vacuity.combiner_optimizer(msr_sets)
        assert sets == [], \
            "Processed empty list should yield empty list."
        assert extract == set(), \
            "Extract of zero constraints should be empty set."

    def test_partly_empty(self):
        msr_sets = [[set()]]
        sets, extract = vacuity.combiner_optimizer(msr_sets)
        assert sets == [[set()]], \
            "Processed empty sets should yield empty set."
        assert extract == set(), \
            "Extract of zero constraints should be empty set."

    def test_single(self):
        msr_sets = [[{"1", "2"}]]
        sets, extract = vacuity.combiner_optimizer(msr_sets)
        assert sets == [[set()]], \
            "Single sets should be optimized into the extract."
        assert extract == {"1", "2"}, \
            "Single sets should be optimized into the extract."

    def test_no_intersection(self):
        msr_sets = [[{"1", "2"}], [{"3", "4"}]]
        sets, extract = vacuity.combiner_optimizer(msr_sets)
        assert sets == [[set()], [set()]], \
            "Single sets should be optimized into the extract."
        assert extract == {"1", "2", "3", "4"}, \
            "Single sets should be optimized into the extract."

    def test_for_intersection(self):
        msr_sets = [[{"1", "2"}, {"2", "3"}], [{"4"}]]
        sets, extract = vacuity.combiner_optimizer(msr_sets)
        assert sets == [[{"1"}, {"3"}], [set()]], \
            "Intersection within the group should be extracted."
        assert extract == {"2", "4"}, \
            "Intersection within the group should be extracted."


class TestTreeWalkerRepair(unittest.TestCase):

    
    def test_example_1_one_result(self):
        tamus = Tamus(
            model_file=THIS_DIR / "fixtures/TestExample-1.xml",
            query_file=THIS_DIR / "fixtures/TestExample-1.q",
            template_name="All",
            args=TEST_ARGS,
        )
        tamus.task = tamus.args.task
        results = []
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
                vacuity.treewalker_repair(tamus, queries, templates, 0, results, tempdir, False)
        pass


class TestCombinerRepair(unittest.TestCase):
    pass


class TestRepair(unittest.TestCase):
    pass
