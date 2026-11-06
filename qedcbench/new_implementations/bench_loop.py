import sys
import os
# import matplotlib
# matplotlib.use('Agg')  # Disables interactive GUI windows entirely
# 1. Add qedclib/qiskit directory to Python path so 'import execute' works
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../qedclib/qiskit')))

# 2. Add qedcbench directory so your local benchmark modules (like deutsch_jozsa) still work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))



from deutsch_jozsa import dj_benchmark
from bernstein_vazirani import bv_benchmark
from hidden_shift import hs_benchmark
from quantum_fourier_transform import qft_benchmark
from grovers import grovers_benchmark
from phase_estimation import pe_benchmark
from hhl import hhl_benchmark
from amplitude_estimation import ae_benchmark
from monte_carlo import mc_benchmark
from hamiltonian_simulation import hamiltonian_simulation_benchmark
from vqe import vqe_benchmark
from shors import shors_benchmark

# New implementation of the benchmark loop --------------------------------

# Benchmark application settings
app_args = dict(
    min_qubits = 2,
    max_qubits = 8,
    skip_qubits = 1,
    max_circuits = 3,
    num_shots = 100,
) 

# Execution settings - for QASM simulator backend - default
exec_args = dict(
    # backend_id = "qasm_simulator",
    backend_id = "fake_sherbrooke",  # fake backend for testing
    exec_options = {"optimization_level": 2, "device": "CPU", "simulation_method": "statevector", "nonesense": "value"},                                       # leave current noise setting unchanged
)

# Loop ------------------------------------------------------------------------------

# benchmarks = [dj_benchmark, bv_benchmark, hs_benchmark, qft_benchmark, grovers_benchmark, pe_benchmark, hhl_benchmark, ae_benchmark, mc_benchmark, hamiltonian_simulation_benchmark, vqe_benchmark, shors_benchmark]
benchmarks = [dj_benchmark, bv_benchmark, hs_benchmark]
fake_backend_ids = ["fake_sherbrooke", "fake_auckland", "fake_aachen"]  # TODO: there are some fake backends in "https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/fake-provider-fake-auckland#qiskit_ibm_runtime.fake_provider" that still need the prefix "v2" to be added to the backend name (like fake_kolkata). The source code does not yet take this into account
optimization_levels = [0, 1, 2, 3]


for benchmark in benchmarks:
    print(f"\n[*] Running benchmark: {benchmark.__name__}")

    for backend_id in fake_backend_ids:
        print(f"\n[*] Running benchmark: {benchmark.__name__} on backend: {backend_id}")
        exec_args["backend_id"] = backend_id

        for optimization_level in optimization_levels:
            print(f"\n[*] Running benchmark: {benchmark.__name__} on backend: {backend_id} with optimization level: {optimization_level}")
            exec_args["exec_options"]["optimization_level"] = optimization_level  # TODO: The optimization level is not yet showing in the plots
            print(f"  - Optimization level: {optimization_level}")
            benchmark.run(**app_args, **exec_args, draw_circuits=False)  # TODO: we still have to take into account the specific arguments for each benchmark, as they may have different required parameters.



# Loop over backend first and then sweep over optimization level and last benchmark.
# export the data_suffix variable to set data_suffix = optimization_level. This way, the data files will not be overwritten when running the same benchmark with different optimization levels. The data_suffix variable is used in the qedclib/qiskit/execute.py file to set the data file name.

# Example:
#  fake_sheerbrooke
#     - optimization_level 0
#         - benchmark 1

# Or with a better structure:
#  fake_sheerbrooke
#     -benchmark 1
#         - optimization_level 0

# during the for loop over the benchmark, do data_suffix = backend_name. Then when looping over the optimization level, do data_suffix = backend_name + "_opt" + str(optimization_level). This way, the data files will not be overwritten when running the same benchmark with different optimization levels. The data_suffix variable is used in the qedclib/qiskit/execute.py file to set the data file name.
# As an alternative, after the loops are done running, we could take the files and structure them as we want.


# Extra: Implement the benchmarks in parallel using multiprocessing to save time.


# Implement script to extract the information from the json files that we want. For example:
# w.r.t to a single benchmark (e.g. dj_benchmark), create a plot then w.r.t to the different backends and optimizaiton levels for the different fidelities


# add the metric: avg_tr_n2qs to the plots (Balken Plots)
# learn how exactly the metrics work
# Think about placong the plots one next to the other to compare optimization levels