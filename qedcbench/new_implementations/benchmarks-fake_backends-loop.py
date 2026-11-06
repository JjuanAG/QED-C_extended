import sys
import os
from datetime import datetime
# import matplotlib
# matplotlib.use('Agg')  # Disables interactive GUI windows entirely
import matplotlib.pyplot as plt

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

from qiskit_aer import Aer, AerSimulator
from qiskit_aer.noise import NoiseModel
from qiskit_ibm_runtime.fake_provider import FakeProviderForBackendV2
from qiskit.providers import Backend
from qiskit import QuantumCircuit, transpile

import logging
import time
from qedclib import metrics
import execute as ex

class BenchmarkResultManager:
    def __init__(self, base_output_dir="."):
        timestamp = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
        self.run_folder_name = f"benchmark_loop_run-{timestamp}"
        self.root_dir = os.path.join(base_output_dir, self.run_folder_name)
        
        os.makedirs(self.root_dir, exist_ok=True)
        print(f"[*] Benchmark results will be saved under: {self.root_dir}")

    def get_target_directory(self, benchmark_name: str, backend_name: str) -> str:
        target_dir = os.path.join(self.root_dir, benchmark_name, backend_name)
        os.makedirs(target_dir, exist_ok=True)
        return target_dir

    def save_and_intercept_plots(self, target_dir: str, prefix: str = "plot"):
        """
        Saves all currently open matplotlib figures to the target directory 
        before they are displayed or cleared.
        """
        fig_nums = plt.get_fignums()
        saved_paths = []
        
        if not fig_nums:
            print(f"[!] Warning: No active matplotlib figures found to save for {prefix}.")
            return saved_paths

        for i, fig_num in enumerate(fig_nums, start=1):
            fig = plt.figure(fig_num)
            file_path = os.path.join(target_dir, f"{prefix}_plot_{i}.png")
            fig.savefig(file_path, bbox_inches='tight', dpi=300)
            saved_paths.append(file_path)
            
        print(f"-> Successfully saved {len(saved_paths)} plots to: {target_dir}")
        return saved_paths


class ConfigurableBackend:
    """
    This class provides methods to configure and select backends for quantum circuit execution.
    """
    def __init__(self, noise_configuration: str, num_qubits: int, device: str, simulation_method: str):
        """
        Initializes the BackendConfigurator with the specified noise configuration, number of qubits, device type, and simulation method.
        """
        self.noise_configuration = noise_configuration
        self.num_qubits = num_qubits
        self.device = device
        self.simulation_method = simulation_method

    @staticmethod
    def split_string(s):
        return s.split(' ', 1)[0]  # Split the string at the first space and return the first part

    def __configure_backend(self, backend: Backend) -> None:
        """
        This method configures the backend with the specified device and simulation method.

        :param backend: Backend to be configured
        :param device: Device type (CPU/GPU)
        :param simulation_method: Simulation method
        """
        backend.set_options(device=self.device)
        backend.set_options(method=self.simulation_method)

    def __get_FakeBackend(self) -> Backend:
            """
            This method returns a fake backend based on the provided noise configuration and number of qubits.

            :param noise_configuration: Noise configuration type
            :param num_qubits: Number of qubits
            :return: Fake backend simulator
            """
            backend_name = str(self.split_string(self.noise_configuration))
            provider = FakeProviderForBackendV2()
            
            try:
                backend = provider.backend(name=backend_name)
            except TypeError:
                filtered_backends = [b for b in provider._backends if b.name == backend_name]  # pylint: disable=W0212
                if not filtered_backends:
                    # Gather all available backend names dynamically
                    available_backends = [b.name for b in provider.backends()]
                    raise ValueError(
                        f"Noise configuration '{backend_name}' not found. "
                        f"Please choose from the available fake backends: {available_backends}"
                    ) from None  # 'from None' prevents messy chained tracebacks if desired
                backend = filtered_backends[0]

            if self.num_qubits > backend.num_qubits:
                logging.warning(f'Requested number of qubits ({self.num_qubits}) exceeds the backend capacity. '
                                f'Using default aer_simulator.')
                return Aer.get_backend("aer_simulator")
                
            noise_model = NoiseModel.from_backend(backend)
            logging.info(f'Using {backend_name} with coupling map: {backend.coupling_map}')
            logging.info(f'Using {backend_name} with noise model: {noise_model}')
            return AerSimulator.from_backend(backend)

    def configured_backend(self) -> Backend:
        """
        This method selects the backend configuration based on the provided noise configuration.

        :param noise_configuration: Noise configuration type
        :param num_qubits: Number of qubits
        :param device: Device type (CPU/GPU)
        :param simulation_method: Simulation method
        :return: Selected backend configuration
        """
        if "fake" in self.noise_configuration:
            backend = self.__get_FakeBackend()
            self.__configure_backend(backend)
            return backend
        elif self.noise_configuration == "No noise":
            aer_simulator = Aer.get_backend("aer_simulator")
            self.__configure_backend(aer_simulator)
            return aer_simulator
        else:
            raise ValueError(f"Unknown noise configuration: {self.noise_configuration}")

MIN_STATE_QUBITS = 1  # for mc_benchmark
num_shots = 100

benchmark_global_configs = {
    "min_qubits": 2,
    "max_qubits": 8,
    "skip_qubits": 1,
    "max_circuits": 3
}

# Define benchmarks with their specific argument overrides
benchmark_specific_configs = [
    {"module": ae_benchmark, "args": {"num_state_qubits": 1, "api": None}},  # Uses defaults
    {"module": bv_benchmark, "args": {"method": 1}},
    {"module": dj_benchmark, "args": {"api": None}},  # Uses defaults
    {"module": grovers_benchmark, "args": {"use_mcx_shim": False, "api": None}},  # Uses defaults
    {"module": hamiltonian_simulation_benchmark, "args": {"method": 1, "hamiltonian": "heisenberg", "use_XX_YY_ZZ_gates": False, "random_pauli_flag": False, "init_state": None, "K": None, "t": None, "api": None}},  # Uses defaults
    {"module": hhl_benchmark, "args": {"method": 1, "use_best_widths": None, "min_register_qubits": 1, "min_input_qubits": None, "max_input_qubits": None, "min_clock_qubits": None, "max_clock_qubits": None, "api": None}},  # Uses defaults
    {"module": hs_benchmark, "args": {"method": 1, "input_value": None, "api": None,}},  # Uses defaults
    {"module": mc_benchmark, "args": {"method": 2, "epsilon": 0.05, "degree": 2, "num_state_qubits": MIN_STATE_QUBITS, "api": None,}},  # Uses defaults
    {"module": pe_benchmark, "args": {"use_midcircuit_measurement": False, "init_phase": None, "api": None}},  # Uses defaults
    {"module": qft_benchmark, "args": {"method": 1, "use_midcircuit_measurement": False, "input_value": None, "api": None}},  # Uses defaults
    {"module": shors_benchmark, "args": {"method": 1, "api": None}},  # Uses defaults. TODO: shors_benchmark does not contain the argument "skip_qubits" in its get_circuits() function
    {"module": vqe_benchmark, "args": {"method": 1, "api": None}}  # Uses defaults
]

backend_configs = [
    {"backend": "fake_sherbrooke", "args": {"num_qubits": benchmark_global_configs["max_qubits"], "device": "CPU", "simulation_method": "statevector"}},
    {"backend": "fake_kolkata", "args": {"num_qubits": benchmark_global_configs["max_qubits"], "device": "CPU", "simulation_method": "statevector"}},
    {"backend": "fake_aachen", "args": {"num_qubits": benchmark_global_configs["max_qubits"], "device": "CPU", "simulation_method": "statevector"}}        
]

optimization_level= 1  


# Benchmark loop: Iterate over each benchmark and each backend, execute the circuits, and collect metrics.

# result_manager = BenchmarkResultManager()

# TODO: Store app metrics and plots inside __data and __images

for benchmark_item in benchmark_specific_configs:
    benchmark = benchmark_item["module"]
    args = benchmark_item["args"]
    print(f"\nRunning benchmark: {str(benchmark)}")
    circuits, metadata = benchmark.get_circuits(**benchmark_global_configs, **args)
    metadata.save_cir
    # Flatten for direct execution
    flat_circuits = [circuits[nq][cid] for nq in circuits if isinstance(circuits[nq], dict) for cid in circuits[nq]]
    
    # Execute the circuits on the configured backend
    for backend_item in backend_configs:
        metadata.pop("subtitle", None)
        metrics.circuit_metrics = metadata
        # Compute gate counts and circuit depth, algorithmic and normalized
        ex.compute_all_circuit_metrics(circuits)
  
        # Configure the backend
        sim_name = backend_item["backend"]
        sim = ConfigurableBackend(sim_name, **backend_item["args"]).configured_backend()

        print(f"\nExecuting on backend: {sim_name} with {len(flat_circuits)} circuits")

        # TODO: loop over optimization levels

        tqc = transpile(flat_circuits, backend=sim, optimization_level=optimization_level)
        ts = time.time()  
        result = sim.run(tqc, shots=num_shots).result()  # Run the circuits on the backend and get the result
        elapsed_time = time.time() - ts

        print(f"Executed {len(flat_circuits)} circuits in {elapsed_time:.3f} secs")
    
        # Define execution handler: called for each circuit to compute and store fidelity.
        def execution_handler(qc, result, num_qubits, circuit_id, num_shots):
            _, fidelity = benchmark.analyze_and_print_result(qc, result, int(num_qubits), int(num_shots),
                    s_int=int(circuit_id))
            metrics.store_metric(num_qubits, circuit_id, 'fidelity', fidelity)

        # Register the handler and process all circuit results.
        # This stores timing metrics and calls execution_handler for each circuit. (for postprocessing)
        ex.init_execution(execution_handler)
        ex.process_circuit_results(circuits, result, elapsed_time=elapsed_time, num_shots=num_shots)

        # Compute statistics for metrics.
        metrics.aggregate_metrics()

        # Plotting --------------------------
        benchmark_name = benchmark.__name__
        provider_name = "IBM"
        device_name = sim_name

        # Set plot titles.
        benchmark_title = f"{benchmark_name}"
        subtitle = f"Benchmark Results - {benchmark_title} {provider_name}"
        metrics.circuit_metrics["subtitle"] = f"device = {device_name}"

        # Determine which metrics to plot.
        filters = ["execute", "fidelity", "hf_fidelity", "depth", "2q", "vbplot"]

        # Generate and show the plots via QED-C metrics
        metrics.plot_metrics(subtitle, filters=filters)

        # Save them into the structured folder path (benchmark / backend / opt_level)
        # target_dir = os.path.join(result_manager.root_dir, benchmark_name, sim_name)
        # os.makedirs(target_dir, exist_ok=True)
        
        # result_manager.save_and_intercept_plots(
        #     target_dir, 
        #     prefix=f"{benchmark_name}_{sim_name}_opt{optimization_level}"
        # )

        # # Clear figures from memory before the next loop iteration
        # plt.close('all')






