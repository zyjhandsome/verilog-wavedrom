"""
Sample Generator - Generate complete sample file sets from parquet dataset.

This script extracts samples from the parquet dataset and generates:
- Original Verilog code (.v)
- Original waveform image (.png)
- Method 1: Simulation-based WaveDrom JSON and PNG
- Method 2: Image extraction-based WaveDrom JSON and PNG
"""

import argparse
import io
import json
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

import config
from convert_dataset import VerilogPipeline
from image_to_wavedrom import VisionAIExtractor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class GenerationStats:
    """Track generation statistics."""
    total: int = 0
    extracted: int = 0
    method1_success: int = 0
    method1_failed: int = 0
    method2_success: int = 0
    method2_failed: int = 0
    
    def summary(self) -> str:
        return (
            f"\nGeneration Summary:\n"
            f"{'='*50}\n"
            f"  Total samples: {self.total}\n"
            f"  Files extracted: {self.extracted}\n"
            f"  Method 1 (simulation): {self.method1_success} success, {self.method1_failed} failed\n"
            f"  Method 2 (image): {self.method2_success} success, {self.method2_failed} failed\n"
            f"{'='*50}"
        )


class SampleGenerator:
    """Generate sample files from parquet dataset."""
    
    def __init__(self, data_dir: Path = None, output_dir: Path = None, match_original: bool = True):
        """Initialize sample generator.
        
        Args:
            data_dir: Path to parquet data directory
            output_dir: Path to output directory
            match_original: If True, generate WaveDrom matching original images
                           (include all signals, use VCD order)
        """
        self.data_dir = data_dir or config.DATA_DIR
        self.output_dir = output_dir or Path("sample_images")
        self.pipeline = VerilogPipeline(match_original=match_original)
        self.stats = GenerationStats()
    
    def load_parquet_samples(self, count: int, seed: int = None) -> List[Dict[str, Any]]:
        """Load specified number of samples from parquet dataset.
        
        Args:
            count: Number of samples to load
            seed: Random seed for reproducible selection
            
        Returns:
            List of sample dictionaries with 'text' and 'image' fields
        """
        try:
            from datasets import load_dataset
            
            logger.info(f"Loading parquet dataset from {self.data_dir}...")
            
            # Load train split
            dataset = load_dataset(
                'parquet',
                data_files={'train': str(self.data_dir / 'train-*.parquet')}
            )['train']
            
            total_samples = len(dataset)
            logger.info(f"Dataset has {total_samples} samples")
            
            # Select samples
            if count >= total_samples:
                indices = list(range(total_samples))
            else:
                if seed is not None:
                    random.seed(seed)
                indices = random.sample(range(total_samples), count)
            
            # Extract selected samples
            samples = []
            for idx in indices:
                sample = dataset[idx]
                samples.append({
                    'index': idx,
                    'text': sample.get('text', ''),
                    'image': sample.get('image')
                })
            
            logger.info(f"Selected {len(samples)} samples")
            return samples
            
        except Exception as e:
            logger.error(f"Failed to load dataset: {e}")
            raise
    
    def extract_original_files(self, sample: Dict[str, Any], sample_name: str) -> bool:
        """Extract original .v and .png files from sample.
        
        Args:
            sample: Sample dictionary with 'text' and 'image' fields
            sample_name: Base name for files (e.g., 'sample_1')
            
        Returns:
            True if extraction successful, False otherwise
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        success = True
        
        # Extract Verilog code
        verilog_code = sample.get('text', '')
        if verilog_code:
            v_path = self.output_dir / f"{sample_name}.v"
            v_path.write_text(verilog_code, encoding='utf-8')
            logger.debug(f"Saved: {v_path}")
        else:
            logger.warning(f"No Verilog code for {sample_name}")
            success = False
        
        # Extract original waveform image
        image = sample.get('image')
        if image is not None:
            png_path = self.output_dir / f"{sample_name}.png"
            try:
                # Handle PIL Image object from datasets
                if hasattr(image, 'save'):
                    image.save(str(png_path), 'PNG')
                # Handle bytes
                elif isinstance(image, bytes):
                    png_path.write_bytes(image)
                # Handle dict with 'bytes' key
                elif isinstance(image, dict) and 'bytes' in image:
                    png_path.write_bytes(image['bytes'])
                else:
                    logger.warning(f"Unknown image format for {sample_name}: {type(image)}")
                    success = False
                    
                if png_path.exists():
                    logger.debug(f"Saved: {png_path}")
            except Exception as e:
                logger.warning(f"Failed to save image for {sample_name}: {e}")
                success = False
        else:
            logger.warning(f"No image for {sample_name}")
            success = False
        
        return success
    
    def run_method1(self, sample_name: str) -> bool:
        """Run Method 1: Simulation-based WaveDrom generation.
        
        Args:
            sample_name: Base name for files (e.g., 'sample_1')
            
        Returns:
            True if successful, False otherwise
        """
        v_path = self.output_dir / f"{sample_name}.v"
        
        if not v_path.exists():
            logger.warning(f"Verilog file not found: {v_path}")
            return False
        
        verilog_code = v_path.read_text(encoding='utf-8')
        
        # Pass original image path for signal order extraction
        original_image_path = self.output_dir / f"{sample_name}.png"
        
        logger.info(f"  Method 1: Running simulation for {sample_name}...")
        return self.pipeline.process_to_files(
            verilog_code, 
            self.output_dir, 
            sample_name,
            original_image_path=original_image_path if original_image_path.exists() else None
        )
    
    def run_method2(self, sample_name: str) -> bool:
        """Run Method 2: Image extraction-based WaveDrom generation.
        
        Args:
            sample_name: Base name for files (e.g., 'sample_1')
            
        Returns:
            True if successful, False otherwise
        """
        png_path = self.output_dir / f"{sample_name}.png"
        
        if not png_path.exists():
            logger.warning(f"Image file not found: {png_path}")
            return False
        
        logger.info(f"  Method 2: Extracting from image for {sample_name}...")
        return VisionAIExtractor.extract_and_render(png_path, self.output_dir, sample_name)
    
    def generate(
        self, 
        count: int, 
        seed: int = None,
        extract_only: bool = False,
        method1_only: bool = False,
        method2_only: bool = False
    ) -> GenerationStats:
        """Generate complete sample file sets.
        
        Args:
            count: Number of samples to generate
            seed: Random seed for reproducible selection
            extract_only: Only extract original files, don't run methods
            method1_only: Only run method 1 (simulation)
            method2_only: Only run method 2 (image extraction)
            
        Returns:
            GenerationStats with results
        """
        # Load samples from parquet
        samples = self.load_parquet_samples(count, seed)
        self.stats.total = len(samples)
        
        for i, sample in enumerate(samples, start=1):
            sample_name = f"sample_{i}"
            logger.info(f"\n[{i}/{len(samples)}] Processing {sample_name}...")
            
            # Step 1: Extract original files
            if self.extract_original_files(sample, sample_name):
                self.stats.extracted += 1
            
            if extract_only:
                continue
            
            # Step 2: Run Method 1 (simulation)
            if not method2_only:
                if self.run_method1(sample_name):
                    self.stats.method1_success += 1
                else:
                    self.stats.method1_failed += 1
            
            # Step 3: Run Method 2 (image extraction)
            if not method1_only:
                if self.run_method2(sample_name):
                    self.stats.method2_success += 1
                else:
                    self.stats.method2_failed += 1
        
        logger.info(self.stats.summary())
        return self.stats
    
    def generate_from_existing(
        self,
        method1_only: bool = False,
        method2_only: bool = False
    ) -> GenerationStats:
        """Run methods on existing extracted files.
        
        Args:
            method1_only: Only run method 1 (simulation)
            method2_only: Only run method 2 (image extraction)
            
        Returns:
            GenerationStats with results
        """
        import re
        
        # Find existing sample files
        sample_pattern = re.compile(r'^sample_(\d+)\.v$')
        
        sample_names = []
        for v_file in sorted(self.output_dir.glob("sample_*.v")):
            match = sample_pattern.match(v_file.name)
            if match:
                sample_names.append(f"sample_{match.group(1)}")
        
        self.stats.total = len(sample_names)
        self.stats.extracted = len(sample_names)
        
        logger.info(f"Found {len(sample_names)} existing samples in {self.output_dir}")
        
        for i, sample_name in enumerate(sample_names, start=1):
            logger.info(f"\n[{i}/{len(sample_names)}] Processing {sample_name}...")
            
            # Run Method 1 (simulation)
            if not method2_only:
                if self.run_method1(sample_name):
                    self.stats.method1_success += 1
                else:
                    self.stats.method1_failed += 1
            
            # Run Method 2 (image extraction)
            if not method1_only:
                if self.run_method2(sample_name):
                    self.stats.method2_success += 1
                else:
                    self.stats.method2_failed += 1
        
        logger.info(self.stats.summary())
        return self.stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate sample files from parquet dataset'
    )
    parser.add_argument(
        '--count', '-n',
        type=int,
        default=15,
        help='Number of samples to generate (default: 15)'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path('sample_images'),
        help='Output directory (default: sample_images/)'
    )
    parser.add_argument(
        '--data-dir',
        type=Path,
        default=None,
        help='Parquet data directory (default: from config)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Random seed for reproducible selection'
    )
    parser.add_argument(
        '--extract-only',
        action='store_true',
        help='Only extract original files, do not run methods'
    )
    parser.add_argument(
        '--method1-only',
        action='store_true',
        help='Only run Method 1 (simulation)'
    )
    parser.add_argument(
        '--method2-only',
        action='store_true',
        help='Only run Method 2 (image extraction)'
    )
    parser.add_argument(
        '--use-existing',
        action='store_true',
        help='Run methods on existing extracted files instead of loading from parquet'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create generator
    generator = SampleGenerator(
        data_dir=args.data_dir,
        output_dir=args.output
    )
    
    # Run generation
    if args.use_existing:
        generator.generate_from_existing(
            method1_only=args.method1_only,
            method2_only=args.method2_only
        )
    else:
        generator.generate(
            count=args.count,
            seed=args.seed,
            extract_only=args.extract_only,
            method1_only=args.method1_only,
            method2_only=args.method2_only
        )


if __name__ == "__main__":
    main()
