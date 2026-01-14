"""
Testbench Generator - Generate Verilog testbenches for simulation.

Creates testbenches that exercise the DUT and generate VCD waveform dumps.
"""

import random
from typing import List, Optional
from verilog_parser import VerilogModule, Port


class TestbenchGenerator:
    """Generate Verilog testbenches for modules."""
    
    def __init__(self, seed: int = None):
        if seed is not None:
            random.seed(seed)
    
    def generate(self, module: VerilogModule) -> str:
        """Generate a testbench for the given module."""
        tb_name = f"tb_{module.name}"
        
        # Generate signal declarations
        signal_decls = self._generate_signal_declarations(module)
        
        # Generate DUT instantiation
        dut_inst = self._generate_dut_instantiation(module)
        
        # Generate stimulus
        stimulus = self._generate_stimulus(module)
        
        # Generate VCD dump
        vcd_dump = self._generate_vcd_dump(module)
        
        testbench = f'''`timescale 1ns/1ps

module {tb_name};

// Signal declarations
{signal_decls}

// DUT instantiation
{dut_inst}

// VCD dump
{vcd_dump}

// Stimulus
{stimulus}

endmodule
'''
        return testbench
    
    def _generate_signal_declarations(self, module: VerilogModule) -> str:
        """Generate reg/wire declarations for testbench signals."""
        lines = []
        
        for port in module.ports:
            if port.direction in ('input', 'inout'):
                # Inputs are driven by testbench, so use reg
                sig_type = 'reg'
            else:
                # Outputs are driven by DUT, so use wire
                sig_type = 'wire'
            
            if port.width > 1:
                lines.append(f"{sig_type} [{port.width-1}:0] {port.name};")
            else:
                lines.append(f"{sig_type} {port.name};")
        
        return '\n'.join(lines)
    
    def _generate_dut_instantiation(self, module: VerilogModule) -> str:
        """Generate DUT instantiation."""
        connections = []
        for port in module.ports:
            connections.append(f"    .{port.name}({port.name})")
        
        connections_str = ',\n'.join(connections)
        
        return f'''{module.name} dut (
{connections_str}
);'''
    
    def _generate_stimulus(self, module: VerilogModule) -> str:
        """Generate stimulus for the testbench."""
        lines = []
        
        # Find clock and reset signals
        clocks = module.get_clock_signals()
        resets = module.get_reset_signals()
        
        # Generate clock if we have one
        if clocks:
            clk = clocks[0]
            lines.append(f'''// Clock generation
always begin
    #{5} {clk.name} = ~{clk.name};
end
''')
        
        # Initial block
        lines.append("initial begin")
        
        # Initialize all inputs
        for port in module.inputs:
            if port.width > 1:
                lines.append(f"    {port.name} = {port.width}'b0;")
            else:
                lines.append(f"    {port.name} = 1'b0;")
        
        lines.append("")
        
        # Reset sequence if we have reset
        if resets:
            rst = resets[0]
            is_active_low = 'n' in rst.name.lower()
            if is_active_low:
                lines.append(f"    // Active low reset sequence")
                lines.append(f"    {rst.name} = 1'b0;")
                lines.append(f"    #20;")
                lines.append(f"    {rst.name} = 1'b1;")
            else:
                lines.append(f"    // Active high reset sequence")
                lines.append(f"    {rst.name} = 1'b1;")
                lines.append(f"    #20;")
                lines.append(f"    {rst.name} = 1'b0;")
            lines.append("")
        
        # Generate random stimulus for other inputs
        other_inputs = [p for p in module.inputs 
                       if p not in clocks and p not in resets]
        
        for i in range(10):  # 10 cycles of random stimulus
            lines.append(f"    // Cycle {i+1}")
            for port in other_inputs:
                if port.width > 1:
                    val = random.randint(0, (1 << min(port.width, 8)) - 1)
                    lines.append(f"    {port.name} = {port.width}'h{val:X};")
                else:
                    val = random.randint(0, 1)
                    lines.append(f"    {port.name} = 1'b{val};")
            lines.append("    #10;")
            lines.append("")
        
        # End simulation
        lines.append("    #50;")
        lines.append("    $finish;")
        lines.append("end")
        
        return '\n'.join(lines)
    
    def _generate_vcd_dump(self, module: VerilogModule) -> str:
        """Generate VCD dump commands."""
        return '''initial begin
    $dumpfile("waveform.vcd");
    $dumpvars(0, dut);
end'''
