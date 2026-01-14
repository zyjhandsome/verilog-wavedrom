"""
Dataset Converter - Main orchestration script for Verilog to WaveDrom conversion.

Reads the existing parquet dataset, runs the full pipeline on each sample,
and creates a new dataset with verilog_code, wavedrom_json, and waveform_image.
"""

import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from tqdm import tqdm

import config
from verilog_parser import parse_verilog, VerilogModule
from testbench_generator import TestbenchGenerator
from simulation_runner import SimulationRunner, SimulationResult
from vcd_to_wavedrom import vcd_to_wavedrom, vcd_to_wavedrom_json
from wavedrom_renderer import WaveDromRenderer, check_dependencies


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ProcessingStats:
    """Track processing statistics."""
    total: int = 0
    success: int = 0
    parse_failed: int = 0
    testbench_failed: int = 0
    simulation_failed: int = 0
    vcd_convert_failed: int = 0
    render_failed: int = 0
    errors: List[Dict[str, str]] = field(default_factory=list)
    
    def log_error(self, index: int, stage: str, message: str):
        self.errors.append({
            'index': index,
            'stage': stage,
            'message': message[:200]  # Truncate long messages
        })
    
    def summary(self) -> str:
        return (
            f"Processing Summary:\n"
            f"  Total: {self.total}\n"
            f"  Success: {self.success} ({100*self.success/max(1,self.total):.1f}%)\n"
            f"  Parse failed: {self.parse_failed}\n"
            f"  Testbench failed: {self.testbench_failed}\n"
            f"  Simulation failed: {self.simulation_failed}\n"
            f"  VCD convert failed: {self.vcd_convert_failed}\n"
            f"  Render failed: {self.render_failed}"
        )


@dataclass
class ProcessedSample:
    """A successfully processed sample."""
    verilog_code: str
    wavedrom_json: str
    waveform_image: bytes
    module_name: str = ""


class VerilogPipeline:
    """Complete pipeline for Verilog to WaveDrom conversion."""
    
    def __init__(self, match_original: bool = True):
        """Initialize pipeline.
        
        Args:
            match_original: If True, include all signals and use VCD order
                           to match original waveform images from the dataset.
        """
        self.tb_generator = TestbenchGenerator()
        self.sim_runner = SimulationRunner()
        self.renderer = WaveDromRenderer()
        self.match_original = match_original
    
    def process_to_files(
        self, 
        verilog_code: str, 
        output_dir: Path, 
        sample_name: str,
        original_image_path: Path = None
    ) -> bool:
        """
        Process Verilog and save results to files.
        
        Method 1: Simulation-based WaveDrom generation.
        
        Args:
            verilog_code: Verilog source code
            output_dir: Directory to save output files
            sample_name: Base name for output files (e.g., 'sample_1')
            original_image_path: Optional path to original waveform image for signal order
            
        Returns:
            True if successful, False otherwise
            
        Output files:
            - {sample_name}_wavedrom.json: WaveDrom JSON
            - {sample_name}_wavedrom.png: Rendered waveform PNG
        """
        result, failed_stage, error_msg = self.process(verilog_code, original_image_path=original_image_path)
        
        if result is None:
            logger.warning(f"Processing failed for {sample_name} at {failed_stage}: {error_msg}")
            return False
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save WaveDrom JSON
        json_path = output_dir / f"{sample_name}_wavedrom.json"
        json_path.write_text(result.wavedrom_json, encoding='utf-8')
        
        # Save rendered PNG
        png_path = output_dir / f"{sample_name}_wavedrom.png"
        png_path.write_bytes(result.waveform_image)
        
        logger.info(f"Saved: {json_path}")
        logger.info(f"Saved: {png_path}")
        
        return True
    
    def process(self, verilog_code: str, index: int = 0, original_image_path: Path = None) -> Optional[ProcessedSample]:
        """
        Process a single Verilog sample through the complete pipeline.
        
        Args:
            verilog_code: Verilog source code
            index: Sample index for logging
            original_image_path: Optional path to original waveform image for signal order
            
        Returns ProcessedSample if successful, None if any stage fails.
        """
        # Stage 1: Parse Verilog
        module = parse_verilog(verilog_code)
        if module is None:
            logger.debug(f"[{index}] Failed to parse Verilog")
            return None, "parse", "Failed to parse Verilog module"
        
        # Stage 2: Generate testbench
        try:
            testbench = self.tb_generator.generate(module)
        except Exception as e:
            logger.debug(f"[{index}] Testbench generation failed: {e}")
            return None, "testbench", str(e)
        
        # Stage 3: Run simulation
        result = self.sim_runner.run(verilog_code, testbench)
        if not result.success:
            logger.debug(f"[{index}] Simulation failed: {result.error_message}")
            return None, "simulation", result.error_message
        
        # Stage 4: Convert VCD to WaveDrom
        try:
            # Get I/O port names for filtering and port definitions for name formatting
            io_port_names = [p.name for p in module.ports]
            wavedrom_dict = vcd_to_wavedrom(
                result.vcd_content, 
                io_port_names=io_port_names,
                port_definitions=module.ports,  # Pass port definitions for signal naming
                match_original=self.match_original  # Match original waveform images
            )
            
            # Stage 4b: Try to reorder signals to match original image
            if original_image_path:
                try:
                    from signal_order_extractor import extract_and_match_order
                    # Also try Verilog file for signal order
                    verilog_path = original_image_path.with_suffix('.v') if original_image_path else None
                    wavedrom_dict = extract_and_match_order(
                        original_image_path, 
                        wavedrom_dict,
                        verilog_path=verilog_path
                    )
                    logger.debug(f"[{index}] Applied signal order")
                except Exception as e:
                    logger.debug(f"[{index}] Signal order extraction failed: {e}")
            
            wavedrom_json = json.dumps(wavedrom_dict)
        except Exception as e:
            logger.debug(f"[{index}] VCD conversion failed: {e}")
            return None, "vcd_convert", str(e)
        
        # Check if we got any signals
        if not wavedrom_dict.get("signal"):
            return None, "vcd_convert", "No signals found in VCD"
        
        # Stage 5: Render to PNG
        try:
            png_bytes = self.renderer.render_to_png(wavedrom_dict)
        except Exception as e:
            logger.debug(f"[{index}] Rendering failed: {e}")
            return None, "render", str(e)
        
        return ProcessedSample(
            verilog_code=verilog_code,
            wavedrom_json=wavedrom_json,
            waveform_image=png_bytes,
            module_name=module.name
        ), None, None


class DatasetConverter:
    """Convert existing dataset to new format with WaveDrom JSON."""
    
    def __init__(self, data_dir: Path = None, output_dir: Path = None):
        self.data_dir = data_dir or config.DATA_DIR
        self.output_dir = output_dir or config.OUTPUT_DIR
        self.pipeline = VerilogPipeline()
        self.stats = ProcessingStats()
    
    def load_dataset(self, subset_size: Optional[int] = None):
        """Load the existing parquet dataset."""
        try:
            from datasets import load_dataset, Dataset
            
            # Load from parquet files
            dataset = load_dataset(
                'parquet',
                data_files={
                    'train': str(self.data_dir / 'train-*.parquet'),
                    'test': str(self.data_dir / 'test-*.parquet')
                }
            )
            
            if subset_size:
                # Take a subset for testing
                dataset['train'] = dataset['train'].select(range(min(subset_size, len(dataset['train']))))
                if 'test' in dataset:
                    dataset['test'] = dataset['test'].select(range(min(subset_size // 5, len(dataset['test']))))
            
            return dataset
            
        except Exception as e:
            logger.error(f"Failed to load dataset: {e}")
            raise
    
    def process_dataset(self, subset_size: Optional[int] = None) -> Dict[str, List]:
        """Process the entire dataset."""
        logger.info("Loading dataset...")
        dataset = self.load_dataset(subset_size)
        
        results = {
            'train': [],
            'test': []
        }
        
        for split in ['train', 'test']:
            if split not in dataset:
                continue
            
            logger.info(f"Processing {split} split ({len(dataset[split])} samples)...")
            
            for i, sample in enumerate(tqdm(dataset[split], desc=f"Processing {split}")):
                self.stats.total += 1
                
                # Get Verilog code from the 'text' field
                verilog_code = sample.get('text', '')
                
                if not verilog_code.strip():
                    self.stats.parse_failed += 1
                    continue
                
                # Process through pipeline
                result, failed_stage, error_msg = self.pipeline.process(verilog_code, i)
                
                if result is None:
                    # Track failure by stage
                    if failed_stage == "parse":
                        self.stats.parse_failed += 1
                    elif failed_stage == "testbench":
                        self.stats.testbench_failed += 1
                    elif failed_stage == "simulation":
                        self.stats.simulation_failed += 1
                    elif failed_stage == "vcd_convert":
                        self.stats.vcd_convert_failed += 1
                    elif failed_stage == "render":
                        self.stats.render_failed += 1
                    
                    self.stats.log_error(i, failed_stage, error_msg)
                    continue
                
                # Success!
                self.stats.success += 1
                results[split].append({
                    'verilog_code': result.verilog_code,
                    'wavedrom_json': result.wavedrom_json,
                    'waveform_image': result.waveform_image
                })
        
        return results
    
    def save_dataset(self, results: Dict[str, List]):
        """Save processed results as a new dataset."""
        from datasets import Dataset, DatasetDict, Features, Value, Image
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Define features for the new dataset
        features = Features({
            'verilog_code': Value('string'),
            'wavedrom_json': Value('string'),
            'waveform_image': Image()
        })
        
        dataset_dict = {}
        
        for split, samples in results.items():
            if not samples:
                continue
            
            # Convert image bytes to PIL Images for the datasets library
            from PIL import Image as PILImage
            import io
            
            processed_samples = []
            for sample in samples:
                img = PILImage.open(io.BytesIO(sample['waveform_image']))
                processed_samples.append({
                    'verilog_code': sample['verilog_code'],
                    'wavedrom_json': sample['wavedrom_json'],
                    'waveform_image': img
                })
            
            dataset_dict[split] = Dataset.from_list(processed_samples, features=features)
        
        if dataset_dict:
            full_dataset = DatasetDict(dataset_dict)
            
            # Save to parquet
            output_path = self.output_dir / "wavedrom_dataset"
            full_dataset.save_to_disk(str(output_path))
            logger.info(f"Dataset saved to: {output_path}")
            
            # Also save as parquet files
            for split, ds in full_dataset.items():
                parquet_path = self.output_dir / f"{split}.parquet"
                ds.to_parquet(str(parquet_path))
                logger.info(f"Parquet saved: {parquet_path}")
    
    def save_stats(self):
        """Save processing statistics."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        stats_file = self.output_dir / "processing_stats.json"
        stats_data = {
            'timestamp': datetime.now().isoformat(),
            'total': self.stats.total,
            'success': self.stats.success,
            'success_rate': self.stats.success / max(1, self.stats.total),
            'failures': {
                'parse': self.stats.parse_failed,
                'testbench': self.stats.testbench_failed,
                'simulation': self.stats.simulation_failed,
                'vcd_convert': self.stats.vcd_convert_failed,
                'render': self.stats.render_failed
            },
            'errors': self.stats.errors[:100]  # Save first 100 errors
        }
        
        stats_file.write_text(json.dumps(stats_data, indent=2))
        logger.info(f"Stats saved to: {stats_file}")


def process_single_file(verilog_path: Path) -> Optional[ProcessedSample]:
    """Process a single Verilog file for testing."""
    pipeline = VerilogPipeline()
    
    verilog_code = verilog_path.read_text(encoding='utf-8')
    result, failed_stage, error_msg = pipeline.process(verilog_code)
    
    if result is None:
        logger.error(f"Failed at {failed_stage}: {error_msg}")
        return None
    
    return result


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert Verilog dataset to WaveDrom format')
    parser.add_argument('--subset', type=int, default=config.SUBSET_SIZE,
                        help='Number of samples to process (0 for all)')
    parser.add_argument('--data-dir', type=Path, default=config.DATA_DIR,
                        help='Input data directory')
    parser.add_argument('--output-dir', type=Path, default=config.OUTPUT_DIR,
                        help='Output directory')
    parser.add_argument('--single', type=Path, default=None,
                        help='Process a single Verilog file')
    parser.add_argument('--check-deps', action='store_true',
                        help='Check dependencies and exit')
    
    args = parser.parse_args()
    
    # Check dependencies
    if args.check_deps:
        print("Checking dependencies...")
        deps = check_dependencies()
        for name, available in deps.items():
            status = "OK" if available else "MISSING"
            print(f"  {name}: {status}")
        
        # Check iverilog
        import shutil
        iverilog_path = shutil.which('iverilog')
        vvp_path = shutil.which('vvp')
        print(f"  iverilog: {'OK' if iverilog_path else 'MISSING'}")
        print(f"  vvp: {'OK' if vvp_path else 'MISSING'}")
        return
    
    # Process single file
    if args.single:
        logger.info(f"Processing single file: {args.single}")
        result = process_single_file(args.single)
        
        if result:
            logger.info(f"Success! Module: {result.module_name}")
            logger.info(f"WaveDrom JSON length: {len(result.wavedrom_json)}")
            logger.info(f"PNG size: {len(result.waveform_image)} bytes")
            
            # Save outputs
            output_dir = args.single.parent
            json_path = output_dir / f"{args.single.stem}_wavedrom.json"
            png_path = output_dir / f"{args.single.stem}_waveform.png"
            
            json_path.write_text(result.wavedrom_json)
            png_path.write_bytes(result.waveform_image)
            
            logger.info(f"Saved: {json_path}")
            logger.info(f"Saved: {png_path}")
        return
    
    # Process dataset
    converter = DatasetConverter(args.data_dir, args.output_dir)
    
    subset = args.subset if args.subset > 0 else None
    results = converter.process_dataset(subset)
    
    logger.info("\n" + converter.stats.summary())
    
    if converter.stats.success > 0:
        converter.save_dataset(results)
    
    converter.save_stats()


if __name__ == "__main__":
    main()
