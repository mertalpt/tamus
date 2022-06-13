from uppaalHelpers.example_generator import generate_nonvacuity_benchmarks

if __name__ == '__main__':
    generate_nonvacuity_benchmarks('./generated-examples', nexamples=10, ntransition=8)
