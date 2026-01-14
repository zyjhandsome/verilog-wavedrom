"""
Validation Script - Extract and validate 10 samples from the dataset.

This script:
1. Extracts 10 random samples from the parquet dataset
2. Runs the full pipeline (simulation + signal order extraction)
3. Compares the generated output with original images
4. Generates a validation report
"""

import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional

from PIL import Image

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import config
from generate_samples import SampleGenerator
from signal_order_extractor import SignalOrderExtractor


@dataclass
class ValidationResult:
    """Result of validating a single sample."""
    sample_name: str
    original_signal_count: int = 0
    generated_signal_count: int = 0
    ocr_signals: List[str] = field(default_factory=list)
    generated_signals: List[str] = field(default_factory=list)
    matched_signals: int = 0
    order_match: bool = False
    success: bool = False
    error: str = ""


def count_signals_in_image(image_path: Path) -> int:
    """Estimate number of signals in a waveform image by counting blue text rows."""
    extractor = SignalOrderExtractor()
    signals = extractor.extract_signal_order(image_path)
    return len(signals)


def get_signals_from_json(json_path: Path) -> List[str]:
    """Get signal names from WaveDrom JSON."""
    if not json_path.exists():
        return []
    data = json.loads(json_path.read_text(encoding='utf-8'))
    return [sig.get('name', '') for sig in data.get('signal', [])]


def validate_sample(output_dir: Path, sample_name: str) -> ValidationResult:
    """Validate a single sample."""
    result = ValidationResult(sample_name=sample_name)
    
    try:
        original_png = output_dir / f"{sample_name}.png"
        generated_json = output_dir / f"{sample_name}_wavedrom.json"
        generated_png = output_dir / f"{sample_name}_wavedrom.png"
        
        # Check if files exist
        if not original_png.exists():
            result.error = "Original PNG not found"
            return result
        
        if not generated_json.exists():
            result.error = "Generated JSON not found"
            return result
        
        # Extract signals from original image
        extractor = SignalOrderExtractor()
        result.ocr_signals = extractor.extract_signal_order(original_png)
        result.original_signal_count = len(result.ocr_signals)
        
        # Get signals from generated JSON
        result.generated_signals = get_signals_from_json(generated_json)
        result.generated_signal_count = len(result.generated_signals)
        
        # Compare signals
        if result.generated_signal_count > 0:
            # Count how many OCR signals match generated signals
            ocr_lower = [s.lower() for s in result.ocr_signals]
            gen_lower = [s.lower() for s in result.generated_signals]
            
            # Simple matching - check if generated signals are in same order as OCR
            matched = 0
            for i, gen_sig in enumerate(gen_lower):
                if i < len(ocr_lower):
                    # Check fuzzy match
                    ocr_sig = ocr_lower[i]
                    # Normalize for comparison
                    gen_base = gen_sig.replace('out_', '').replace('[', '').replace(']', '').replace(':', '')
                    ocr_base = ocr_sig.replace('[', '').replace(']', '').replace(':', '')
                    if gen_base in ocr_base or ocr_base in gen_base or gen_base == ocr_base:
                        matched += 1
            
            result.matched_signals = matched
            result.order_match = matched >= len(result.generated_signals) * 0.8  # 80% match threshold
            result.success = result.order_match and result.generated_signal_count > 0
        
    except Exception as e:
        result.error = str(e)
    
    return result


def run_validation(num_samples: int = 10, seed: int = 42):
    """Run validation on specified number of samples."""
    print(f"=" * 60)
    print(f"Verilog-WaveDrom Signal Order Extraction Validation")
    print(f"=" * 60)
    print(f"Samples: {num_samples}, Seed: {seed}")
    print()
    
    # Create output directory
    output_dir = Path("validation_output")
    output_dir.mkdir(exist_ok=True)
    
    # Initialize generator
    generator = SampleGenerator(output_dir=output_dir)
    
    # Generate samples
    print(f"Step 1: Extracting {num_samples} samples from dataset...")
    print("-" * 60)
    
    stats = generator.generate(
        count=num_samples,
        seed=seed,
        method1_only=True  # Only use simulation method
    )
    
    print()
    print(f"Step 2: Validating signal extraction...")
    print("-" * 60)
    
    # Validate each sample
    results = []
    for i in range(1, num_samples + 1):
        sample_name = f"sample_{i}"
        print(f"  Validating {sample_name}...", end=" ")
        result = validate_sample(output_dir, sample_name)
        results.append(result)
        
        if result.success:
            print(f"✓ ({result.matched_signals}/{result.generated_signal_count} signals matched)")
        elif result.error:
            print(f"✗ Error: {result.error}")
        else:
            print(f"△ Partial ({result.matched_signals}/{result.generated_signal_count} matched)")
    
    # Generate report
    print()
    print(f"=" * 60)
    print(f"VALIDATION REPORT")
    print(f"=" * 60)
    
    success_count = sum(1 for r in results if r.success)
    partial_count = sum(1 for r in results if not r.success and not r.error and r.generated_signal_count > 0)
    error_count = sum(1 for r in results if r.error)
    
    print(f"\nSummary:")
    print(f"  Total samples: {num_samples}")
    print(f"  Successful: {success_count} ({100*success_count/num_samples:.1f}%)")
    print(f"  Partial match: {partial_count} ({100*partial_count/num_samples:.1f}%)")
    print(f"  Errors: {error_count} ({100*error_count/num_samples:.1f}%)")
    
    print(f"\nDetailed Results:")
    print(f"-" * 60)
    print(f"{'Sample':<12} {'OCR':<5} {'Gen':<5} {'Match':<6} {'Order':<6} {'Status':<10}")
    print(f"-" * 60)
    
    for r in results:
        status = "✓ OK" if r.success else ("✗ Error" if r.error else "△ Partial")
        order = "Yes" if r.order_match else "No"
        print(f"{r.sample_name:<12} {r.original_signal_count:<5} {r.generated_signal_count:<5} "
              f"{r.matched_signals:<6} {order:<6} {status:<10}")
    
    print(f"-" * 60)
    
    # Save detailed results
    report_path = output_dir / "validation_report.json"
    report_data = {
        "summary": {
            "total": num_samples,
            "successful": success_count,
            "partial": partial_count,
            "errors": error_count,
            "success_rate": success_count / num_samples
        },
        "results": [
            {
                "sample_name": r.sample_name,
                "ocr_signals": r.ocr_signals,
                "generated_signals": r.generated_signals,
                "matched_signals": r.matched_signals,
                "order_match": r.order_match,
                "success": r.success,
                "error": r.error
            }
            for r in results
        ]
    }
    report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False))
    print(f"\nDetailed report saved to: {report_path}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate signal order extraction')
    parser.add_argument('-n', '--num-samples', type=int, default=10,
                        help='Number of samples to validate (default: 10)')
    parser.add_argument('-s', '--seed', type=int, default=42,
                        help='Random seed for sample selection (default: 42)')
    
    args = parser.parse_args()
    
    run_validation(args.num_samples, args.seed)
