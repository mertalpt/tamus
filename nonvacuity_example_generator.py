from uppaalHelpers.example_generator import generate_nonvacuity_benchmarks

if __name__ == '__main__':
    generate_nonvacuity_benchmarks(
        './generated-examples',
        nexamples=10,
        enforce_vacuity=True,
        max_considered_example_count=100,
        nclock=6,
        nautomata=10,
        nlocation=20,
        ntransition=40,
    )
