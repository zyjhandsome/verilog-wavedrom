"""
Simulation Runner - Run Verilog simulations using Icarus Verilog.

Compiles Verilog code and testbenches, runs simulation, and captures VCD output.
"""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import config


@dataclass
class SimulationResult:
    """Result of a simulation run."""
    success: bool
    vcd_content: str = ""
    error_message: str = ""
    compile_output: str = ""
    run_output: str = ""


class SimulationRunner:
    """Run Verilog simulations using Icarus Verilog."""
    
    def __init__(self, timeout: int = None):
        self.timeout = timeout or config.SIMULATION_TIMEOUT
        self.iverilog_path = shutil.which('iverilog')
        self.vvp_path = shutil.which('vvp')
    
    def check_tools(self) -> bool:
        """Check if simulation tools are available."""
        return self.iverilog_path is not None and self.vvp_path is not None
    
    def run(self, verilog_code: str, testbench_code: str) -> SimulationResult:
        """Run simulation and return VCD content."""
        if not self.check_tools():
            return SimulationResult(
                success=False,
                error_message="Icarus Verilog (iverilog/vvp) not found in PATH"
            )
        
        # Create temporary directory for simulation files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Write source files
            dut_file = tmpdir / "dut.v"
            tb_file = tmpdir / "testbench.v"
            dut_file.write_text(verilog_code, encoding='utf-8')
            tb_file.write_text(testbench_code, encoding='utf-8')
            
            # Compile
            out_file = tmpdir / "sim.out"
            compile_result = self._compile(dut_file, tb_file, out_file)
            
            if not compile_result.success:
                return compile_result
            
            # Run simulation
            vcd_file = tmpdir / "waveform.vcd"
            run_result = self._run_simulation(out_file, tmpdir)
            
            if not run_result.success:
                return run_result
            
            # Read VCD file
            if vcd_file.exists():
                vcd_content = vcd_file.read_text(encoding='utf-8')
                return SimulationResult(
                    success=True,
                    vcd_content=vcd_content,
                    compile_output=compile_result.compile_output,
                    run_output=run_result.run_output
                )
            else:
                return SimulationResult(
                    success=False,
                    error_message="VCD file not generated",
                    compile_output=compile_result.compile_output,
                    run_output=run_result.run_output
                )
    
    def _compile(self, dut_file: Path, tb_file: Path, out_file: Path) -> SimulationResult:
        """Compile Verilog files."""
        try:
            result = subprocess.run(
                [self.iverilog_path, '-o', str(out_file), str(dut_file), str(tb_file)],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode != 0:
                return SimulationResult(
                    success=False,
                    error_message=f"Compilation failed: {result.stderr}",
                    compile_output=result.stdout + result.stderr
                )
            
            return SimulationResult(
                success=True,
                compile_output=result.stdout + result.stderr
            )
            
        except subprocess.TimeoutExpired:
            return SimulationResult(
                success=False,
                error_message="Compilation timed out"
            )
        except Exception as e:
            return SimulationResult(
                success=False,
                error_message=f"Compilation error: {str(e)}"
            )
    
    def _run_simulation(self, out_file: Path, work_dir: Path) -> SimulationResult:
        """Run the compiled simulation."""
        try:
            result = subprocess.run(
                [self.vvp_path, str(out_file)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(work_dir)
            )
            
            # vvp may return non-zero even on success with $finish
            return SimulationResult(
                success=True,
                run_output=result.stdout + result.stderr
            )
            
        except subprocess.TimeoutExpired:
            return SimulationResult(
                success=False,
                error_message="Simulation timed out"
            )
        except Exception as e:
            return SimulationResult(
                success=False,
                error_message=f"Simulation error: {str(e)}"
            )
