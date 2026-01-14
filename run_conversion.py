#!/usr/bin/env python3
"""
Unified Conversion Script - 统一的波形转换入口

从 parquet 数据集提取样本，使用两种方法进行 WaveDrom 转换：
- 方法一 (Simulation): 通过 Verilog 仿真生成 WaveDrom
- 方法二 (Extraction): 从原始波形图像提取 WaveDrom

输出文件结构:
sample_images/
├── sample_1.v              # 原始 Verilog
├── sample_1.png            # 原始波形图
├── sample_1_wavedrom.json  # 方法一输出
├── sample_1_wavedrom.png   # 方法一渲染
├── sample_1_extracted.json # 方法二输出 
├── sample_1_extracted.png  # 方法二渲染
└── ...
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """单个样本的转换结果"""
    sample_name: str
    verilog_extracted: bool = False
    image_extracted: bool = False
    method1_success: bool = False
    method1_error: str = ""
    method2_success: bool = False
    method2_error: str = ""


@dataclass
class ConversionReport:
    """批量转换报告"""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_samples: int = 0
    extraction_success: int = 0
    method1_success: int = 0
    method1_failed: int = 0
    method2_success: int = 0
    method2_failed: int = 0
    results: List[ConversionResult] = field(default_factory=list)
    
    def add_result(self, result: ConversionResult):
        self.results.append(result)
        self.total_samples += 1
        if result.verilog_extracted and result.image_extracted:
            self.extraction_success += 1
        if result.method1_success:
            self.method1_success += 1
        elif result.method1_error:
            self.method1_failed += 1
        if result.method2_success:
            self.method2_success += 1
        elif result.method2_error:
            self.method2_failed += 1
    
    def finalize(self):
        self.end_time = datetime.now()
    
    def summary(self) -> str:
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time else 0
        return f"""
╔══════════════════════════════════════════════════════════════╗
║                     转换报告 (Conversion Report)              ║
╠══════════════════════════════════════════════════════════════╣
║  总样本数:          {self.total_samples:>5}                                   ║
║  文件提取成功:      {self.extraction_success:>5}                                   ║
║                                                              ║
║  方法一 (仿真):                                               ║
║    成功:            {self.method1_success:>5}                                   ║
║    失败:            {self.method1_failed:>5}                                   ║
║    成功率:          {100*self.method1_success/max(1,self.method1_success+self.method1_failed):>5.1f}%                                  ║
║                                                              ║
║  方法二 (图像提取):                                           ║
║    成功:            {self.method2_success:>5}                                   ║
║    失败:            {self.method2_failed:>5}                                   ║
║    成功率:          {100*self.method2_success/max(1,self.method2_success+self.method2_failed):>5.1f}%                                  ║
║                                                              ║
║  处理时间:          {duration:>5.1f} 秒                                 ║
╚══════════════════════════════════════════════════════════════╝
"""
    
    def to_json(self) -> Dict[str, Any]:
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.end_time else None,
            "summary": {
                "total_samples": self.total_samples,
                "extraction_success": self.extraction_success,
                "method1_success": self.method1_success,
                "method1_failed": self.method1_failed,
                "method2_success": self.method2_success,
                "method2_failed": self.method2_failed
            },
            "results": [
                {
                    "sample_name": r.sample_name,
                    "verilog_extracted": r.verilog_extracted,
                    "image_extracted": r.image_extracted,
                    "method1_success": r.method1_success,
                    "method1_error": r.method1_error,
                    "method2_success": r.method2_success,
                    "method2_error": r.method2_error
                }
                for r in self.results
            ]
        }


class UnifiedConverter:
    """统一的波形转换器"""
    
    def __init__(
        self,
        data_dir: Path = None,
        output_dir: Path = None,
        match_original: bool = True
    ):
        """
        初始化转换器
        
        Args:
            data_dir: parquet 数据目录
            output_dir: 输出目录
            match_original: 是否匹配原始波形顺序
        """
        import config
        self.data_dir = data_dir or config.DATA_DIR
        self.output_dir = output_dir or Path("sample_images")
        self.match_original = match_original
        
        # 延迟加载转换器
        self._pipeline = None
        self._extractor = None
    
    @property
    def pipeline(self):
        """延迟加载方法一流水线"""
        if self._pipeline is None:
            from convert_dataset import VerilogPipeline
            self._pipeline = VerilogPipeline(match_original=self.match_original)
        return self._pipeline
    
    @property
    def extractor(self):
        """延迟加载方法二提取器"""
        if self._extractor is None:
            from image_to_wavedrom import VisionAIExtractor
            self._extractor = VisionAIExtractor
        return self._extractor
    
    def load_samples(self, count: int, seed: int = None, indices: List[int] = None) -> List[Dict[str, Any]]:
        """
        从 parquet 数据集加载样本
        
        Args:
            count: 样本数量
            seed: 随机种子
            indices: 指定的样本索引列表（优先使用）
            
        Returns:
            样本列表
        """
        import random
        from datasets import load_dataset
        
        logger.info(f"正在加载数据集: {self.data_dir}")
        
        dataset = load_dataset(
            'parquet',
            data_files={'train': str(self.data_dir / 'train-*.parquet')}
        )['train']
        
        total = len(dataset)
        logger.info(f"数据集共有 {total} 个样本")
        
        # 确定要加载的索引
        if indices:
            selected_indices = [i for i in indices if i < total]
        else:
            if count >= total:
                selected_indices = list(range(total))
            else:
                if seed is not None:
                    random.seed(seed)
                selected_indices = random.sample(range(total), count)
        
        samples = []
        for idx in selected_indices:
            sample = dataset[idx]
            samples.append({
                'index': idx,
                'text': sample.get('text', ''),
                'image': sample.get('image')
            })
        
        logger.info(f"已选择 {len(samples)} 个样本")
        return samples
    
    def extract_files(self, sample: Dict[str, Any], sample_name: str) -> tuple:
        """
        从样本提取原始文件
        
        Args:
            sample: 样本数据
            sample_name: 样本名称
            
        Returns:
            (verilog_ok, image_ok) 提取结果
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        verilog_ok = False
        image_ok = False
        
        # 提取 Verilog 代码
        verilog_code = sample.get('text', '')
        if verilog_code:
            v_path = self.output_dir / f"{sample_name}.v"
            v_path.write_text(verilog_code, encoding='utf-8')
            logger.debug(f"已保存: {v_path}")
            verilog_ok = True
        
        # 提取波形图像
        image = sample.get('image')
        if image is not None:
            png_path = self.output_dir / f"{sample_name}.png"
            try:
                if hasattr(image, 'save'):
                    image.save(str(png_path), 'PNG')
                elif isinstance(image, bytes):
                    png_path.write_bytes(image)
                elif isinstance(image, dict) and 'bytes' in image:
                    png_path.write_bytes(image['bytes'])
                
                if png_path.exists():
                    logger.debug(f"已保存: {png_path}")
                    image_ok = True
            except Exception as e:
                logger.warning(f"保存图像失败 {sample_name}: {e}")
        
        return verilog_ok, image_ok
    
    def run_method1(self, sample_name: str) -> tuple:
        """
        运行方法一：基于仿真的转换
        
        Args:
            sample_name: 样本名称
            
        Returns:
            (success, error_msg)
        """
        v_path = self.output_dir / f"{sample_name}.v"
        
        if not v_path.exists():
            return False, "Verilog 文件不存在"
        
        verilog_code = v_path.read_text(encoding='utf-8')
        original_image = self.output_dir / f"{sample_name}.png"
        
        try:
            success = self.pipeline.process_to_files(
                verilog_code=verilog_code,
                output_dir=self.output_dir,
                sample_name=sample_name,
                original_image_path=original_image if original_image.exists() else None
            )
            
            if success:
                return True, ""
            else:
                return False, "处理失败"
        except Exception as e:
            return False, str(e)
    
    def run_method2(self, sample_name: str) -> tuple:
        """
        运行方法二：基于图像提取的转换
        
        Args:
            sample_name: 样本名称
            
        Returns:
            (success, error_msg)
        """
        png_path = self.output_dir / f"{sample_name}.png"
        
        if not png_path.exists():
            return False, "图像文件不存在"
        
        try:
            success = self.extractor.extract_and_render(
                image_path=png_path,
                output_dir=self.output_dir,
                sample_name=sample_name
            )
            
            if success:
                return True, ""
            else:
                return False, "提取失败"
        except ValueError as e:
            return False, f"无预定义提取器: {e}"
        except Exception as e:
            return False, str(e)
    
    def convert_samples(
        self,
        count: int = 5,
        seed: int = None,
        indices: List[int] = None,
        run_method1: bool = True,
        run_method2: bool = True,
        extract_only: bool = False
    ) -> ConversionReport:
        """
        批量转换样本
        
        Args:
            count: 样本数量
            seed: 随机种子
            indices: 指定的样本索引
            run_method1: 是否运行方法一
            run_method2: 是否运行方法二
            extract_only: 仅提取原始文件
            
        Returns:
            转换报告
        """
        report = ConversionReport()
        
        # 加载样本
        samples = self.load_samples(count, seed, indices)
        
        for i, sample in enumerate(samples, start=1):
            sample_name = f"sample_{i}"
            result = ConversionResult(sample_name=sample_name)
            
            logger.info(f"\n[{i}/{len(samples)}] 处理 {sample_name} (原始索引: {sample['index']})")
            
            # Step 1: 提取原始文件
            result.verilog_extracted, result.image_extracted = self.extract_files(sample, sample_name)
            
            if extract_only:
                report.add_result(result)
                continue
            
            # Step 2: 运行方法一
            if run_method1:
                logger.info(f"  方法一: 仿真转换...")
                result.method1_success, result.method1_error = self.run_method1(sample_name)
                if result.method1_success:
                    logger.info(f"  方法一: ✓ 成功")
                else:
                    logger.warning(f"  方法一: ✗ 失败 - {result.method1_error}")
            
            # Step 3: 运行方法二
            if run_method2:
                logger.info(f"  方法二: 图像提取...")
                result.method2_success, result.method2_error = self.run_method2(sample_name)
                if result.method2_success:
                    logger.info(f"  方法二: ✓ 成功")
                else:
                    logger.warning(f"  方法二: ✗ 失败 - {result.method2_error}")
            
            report.add_result(result)
        
        report.finalize()
        return report
    
    def convert_existing(
        self,
        run_method1: bool = True,
        run_method2: bool = True
    ) -> ConversionReport:
        """
        对已提取的文件运行转换
        
        Args:
            run_method1: 是否运行方法一
            run_method2: 是否运行方法二
            
        Returns:
            转换报告
        """
        import re
        
        report = ConversionReport()
        sample_pattern = re.compile(r'^sample_(\d+)\.v$')
        
        # 查找已有的样本文件
        sample_names = []
        for v_file in sorted(self.output_dir.glob("sample_*.v")):
            match = sample_pattern.match(v_file.name)
            if match:
                sample_names.append(f"sample_{match.group(1)}")
        
        logger.info(f"找到 {len(sample_names)} 个已有样本")
        
        for i, sample_name in enumerate(sample_names, start=1):
            result = ConversionResult(sample_name=sample_name)
            result.verilog_extracted = True
            result.image_extracted = (self.output_dir / f"{sample_name}.png").exists()
            
            logger.info(f"\n[{i}/{len(sample_names)}] 处理 {sample_name}")
            
            # 运行方法一
            if run_method1:
                logger.info(f"  方法一: 仿真转换...")
                result.method1_success, result.method1_error = self.run_method1(sample_name)
                if result.method1_success:
                    logger.info(f"  方法一: ✓ 成功")
                else:
                    logger.warning(f"  方法一: ✗ 失败 - {result.method1_error}")
            
            # 运行方法二
            if run_method2:
                logger.info(f"  方法二: 图像提取...")
                result.method2_success, result.method2_error = self.run_method2(sample_name)
                if result.method2_success:
                    logger.info(f"  方法二: ✓ 成功")
                else:
                    logger.warning(f"  方法二: ✗ 失败 - {result.method2_error}")
            
            report.add_result(result)
        
        report.finalize()
        return report


def check_dependencies():
    """检查依赖是否已安装"""
    import shutil
    
    print("检查依赖...")
    print("-" * 40)
    
    # Python 包
    python_deps = {
        'datasets': False,
        'wavedrom': False,
        'playwright': False,
        'cairosvg': False,
        'PIL': False,
        'tqdm': False,
    }
    
    for pkg in python_deps:
        try:
            if pkg == 'PIL':
                import PIL
            else:
                __import__(pkg)
            python_deps[pkg] = True
        except ImportError:
            pass
    
    print("Python 包:")
    for pkg, ok in python_deps.items():
        status = "✓" if ok else "✗"
        print(f"  {status} {pkg}")
    
    # 系统工具
    print("\n系统工具:")
    system_deps = {
        'iverilog': shutil.which('iverilog') is not None,
        'vvp': shutil.which('vvp') is not None,
        'npx': shutil.which('npx') is not None,
    }
    
    for tool, ok in system_deps.items():
        status = "✓" if ok else "✗"
        print(f"  {status} {tool}")
    
    # 检查关键依赖
    critical_missing = []
    if not python_deps['datasets']:
        critical_missing.append('datasets (pip install datasets)')
    if not python_deps['wavedrom']:
        critical_missing.append('wavedrom (pip install wavedrom)')
    if not system_deps['iverilog']:
        critical_missing.append('iverilog (方法一需要)')
    
    if critical_missing:
        print("\n" + "=" * 40)
        print("缺少关键依赖:")
        for dep in critical_missing:
            print(f"  - {dep}")
        return False
    
    print("\n" + "=" * 40)
    print("所有关键依赖已就绪!")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Verilog 波形图到 WaveDrom 转换工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 生成 5 个样本，运行两种方法
  python run_conversion.py --count 5
  
  # 仅运行方法一（仿真）
  python run_conversion.py --count 10 --method1-only
  
  # 仅运行方法二（图像提取）
  python run_conversion.py --count 5 --method2-only
  
  # 仅提取原始文件
  python run_conversion.py --count 20 --extract-only
  
  # 对已有文件运行转换
  python run_conversion.py --use-existing
  
  # 指定输出目录
  python run_conversion.py --count 5 -o my_output/
  
  # 检查依赖
  python run_conversion.py --check-deps
"""
    )
    
    parser.add_argument(
        '--count', '-n',
        type=int,
        default=5,
        help='处理样本数量 (默认: 5)'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path('sample_images'),
        help='输出目录 (默认: sample_images/)'
    )
    parser.add_argument(
        '--data-dir',
        type=Path,
        default=None,
        help='parquet 数据目录'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='随机种子 (可重复选择)'
    )
    parser.add_argument(
        '--indices',
        type=int,
        nargs='+',
        default=None,
        help='指定样本索引 (如: --indices 0 5 10)'
    )
    parser.add_argument(
        '--extract-only',
        action='store_true',
        help='仅提取原始文件'
    )
    parser.add_argument(
        '--method1-only',
        action='store_true',
        help='仅运行方法一 (仿真)'
    )
    parser.add_argument(
        '--method2-only',
        action='store_true',
        help='仅运行方法二 (图像提取)'
    )
    parser.add_argument(
        '--use-existing',
        action='store_true',
        help='对已有文件运行转换'
    )
    parser.add_argument(
        '--check-deps',
        action='store_true',
        help='检查依赖并退出'
    )
    parser.add_argument(
        '--save-report',
        action='store_true',
        help='保存 JSON 报告'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='详细日志'
    )
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 检查依赖
    if args.check_deps:
        sys.exit(0 if check_dependencies() else 1)
    
    # 确定运行哪些方法
    run_method1 = not args.method2_only
    run_method2 = not args.method1_only
    
    # 创建转换器
    converter = UnifiedConverter(
        data_dir=args.data_dir,
        output_dir=args.output
    )
    
    # 运行转换
    if args.use_existing:
        report = converter.convert_existing(
            run_method1=run_method1,
            run_method2=run_method2
        )
    else:
        report = converter.convert_samples(
            count=args.count,
            seed=args.seed,
            indices=args.indices,
            run_method1=run_method1,
            run_method2=run_method2,
            extract_only=args.extract_only
        )
    
    # 输出报告
    print(report.summary())
    
    # 保存报告
    if args.save_report:
        report_path = args.output / "conversion_report.json"
        report_path.write_text(json.dumps(report.to_json(), indent=2, ensure_ascii=False))
        print(f"报告已保存: {report_path}")


if __name__ == "__main__":
    main()
