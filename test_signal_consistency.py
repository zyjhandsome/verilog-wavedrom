"""Test script to verify signal naming consistency."""

import json
from pathlib import Path
from verilog_parser import parse_verilog
from testbench_generator import TestbenchGenerator
from simulation_runner import SimulationRunner
from vcd_to_wavedrom import vcd_to_wavedrom
from wavedrom_renderer import WaveDromRenderer


def test_sample(sample_path: Path):
    """Test signal naming for a single sample."""
    print(f"\n{'='*60}")
    print(f"Testing: {sample_path}")
    print('='*60)
    
    # Read Verilog
    verilog_code = sample_path.read_text(encoding='utf-8')
    
    # Parse
    module = parse_verilog(verilog_code)
    if module is None:
        print("ERROR: Failed to parse Verilog")
        return False
    
    print(f"\nModule: {module.name}")
    print("\nPort definitions (from parser):")
    for i, p in enumerate(module.ports):
        print(f"  [{i}] {p.direction:6} {p.get_full_name():20} (width={p.width})")
    
    # Generate testbench
    tb_gen = TestbenchGenerator()
    testbench = tb_gen.generate(module)
    
    # Run simulation
    sim = SimulationRunner()
    result = sim.run(verilog_code, testbench)
    print(f"\nSimulation: {'success' if result.success else 'FAILED'}")
    
    if not result.success:
        print(f"Error: {result.error_message}")
        return False
    
    # Convert to WaveDrom (match_original=True to include all signals in VCD order)
    wavedrom = vcd_to_wavedrom(
        result.vcd_content,
        io_port_names=[p.name for p in module.ports],
        port_definitions=module.ports,
        match_original=True  # Include all signals in VCD order to match original images
    )
    
    print("\nWaveDrom signals (after conversion):")
    for i, sig in enumerate(wavedrom['signal']):
        print(f"  [{i}] {sig['name']}")
    
    # Save JSON for inspection
    output_path = sample_path.parent / f"{sample_path.stem}_wavedrom.json"
    output_path.write_text(json.dumps(wavedrom, indent=2))
    print(f"\nSaved: {output_path}")
    
    # Render and save PNG
    try:
        renderer = WaveDromRenderer()
        png_bytes = renderer.render_to_png(wavedrom)
        png_path = sample_path.parent / f"{sample_path.stem}_wavedrom.png"
        png_path.write_bytes(png_bytes)
        print(f"Saved: {png_path} ({len(png_bytes)} bytes)")
    except Exception as e:
        print(f"PNG rendering failed: {e}")
    
    # Verify signal names match port definitions
    print("\n--- Signal Consistency Check ---")
    port_names = [p.get_full_name() for p in module.ports]
    signal_names = [s['name'] for s in wavedrom['signal']]
    
    # Check if signals have bit ranges
    has_bit_ranges = any('[' in name for name in signal_names)
    print(f"Signals with bit ranges: {has_bit_ranges}")
    
    # Check order
    expected_order_match = True
    for i, sig_name in enumerate(signal_names):
        if i < len(port_names):
            expected = port_names[i]
            if sig_name != expected:
                print(f"  Mismatch at [{i}]: got '{sig_name}', expected '{expected}'")
                expected_order_match = False
    
    print(f"Signal order matches port order: {expected_order_match}")
    
    return True


def main():
    sample_dir = Path("sample_images")
    
    # Find all .v files
    samples = sorted(sample_dir.glob("sample_*.v"))
    
    if not samples:
        print("No samples found in sample_images/")
        return
    
    success = 0
    for sample in samples:
        if test_sample(sample):
            success += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {success}/{len(samples)} samples tested successfully")
    print('='*60)


if __name__ == "__main__":
    main()
