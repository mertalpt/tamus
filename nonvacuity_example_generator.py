import argparse
import datetime
import os

from uppaalHelpers.example_generator import generate_nonvacuity_benchmarks

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-example", action="store", type=int, default=1)
    parser.add_argument("--num-clock", action="store", type=int, default=1)
    parser.add_argument("--num-automata", action="store", type=int, default=2)
    parser.add_argument("--num-location", action="store", type=int, default=3)
    parser.add_argument("--num-transition", action="store", type=int, default=5)
    parser.add_argument("--out-dir", action="store", type=str, default=None)
    parser.add_argument("--out-dir-override", action="store", type=str, default=None)
    parser.add_argument("--enforce-vacuity", action="store_true", default=False)
    parser.add_argument("--check-limit", action="store", type=int, default=1000)

    args = parser.parse_args()

    out_dir = args.out_dir or "."
    if out_dir[-1] != "/":
        out_dir = out_dir + "/"
    timestamp = int(datetime.datetime.utcnow().timestamp())
    out_dir = f"{out_dir}Examples-{timestamp}"

    if args.out_dir_override is not None:
        out_dir = args.out_dir_override

    if not os.path.exists(out_dir):
        os.mkdir(out_dir)

    generate_nonvacuity_benchmarks(
        out_dir_path=out_dir,
        nexamples=args.num_example,
        enforce_vacuity=args.enforce_vacuity,
        max_considered_example_count=args.check_limit,
        nclock=args.num_clock,
        nautomata=args.num_automata,
        nlocation=args.num_location,
        ntransition=args.num_transition,
    )
