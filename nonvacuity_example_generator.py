from uppaalHelpers.example_generator import generate_nonvacuity_benchmarks

if __name__ == '__main__':
    generate_nonvacuity_benchmarks(
        './generated-examples',
        nexamples=6,
        enforce_vacuity=True,
        max_considered_example_count=10000,
        nclock=5,
        nautomata=6,
        nlocation=10,
        ntransition=15,
    )
