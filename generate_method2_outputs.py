#!/usr/bin/env python3
"""
Generate Method 2 (Image Extraction) Outputs

生成方法二（图像提取）的输出文件：
- sample_X_extracted.json
- sample_X_extracted.png

使用方法:
    python generate_method2_outputs.py                    # 处理所有样本
    python generate_method2_outputs.py --samples 1 2 3    # 处理指定样本
    python generate_method2_outputs.py --list             # 列出可用的提取器
"""

import argparse
import json
import logging
import re
from pathlib import Path

from image_to_wavedrom import VisionAIExtractor
from wavedrom_renderer import WaveDromRenderer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def list_available_extractors():
    """列出所有可用的提取器"""
    print("\n可用的预定义提取器:")
    print("-" * 40)
    for name in sorted(VisionAIExtractor._extractors.keys()):
        print(f"  ✓ {name}")
    print("-" * 40)


def generate_extracted_files(
    output_dir: Path,
    sample_numbers: list = None
):
    """
    生成方法二的输出文件
    
    Args:
        output_dir: 输出目录
        sample_numbers: 要处理的样本编号列表（None 表示全部）
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    renderer = WaveDromRenderer()
    
    # 收集要处理的样本
    samples_to_process = []
    
    if sample_numbers:
        # 处理指定的样本
        for num in sample_numbers:
            image_name = f"sample_{num}.png"
            if image_name in VisionAIExtractor._extractors:
                samples_to_process.append((num, image_name))
            else:
                logger.warning(f"样本 {num} 没有预定义的提取器")
    else:
        # 处理所有有提取器的样本
        pattern = re.compile(r'sample_(\d+)\.png')
        for image_name in VisionAIExtractor._extractors.keys():
            match = pattern.match(image_name)
            if match:
                num = int(match.group(1))
                samples_to_process.append((num, image_name))
    
    samples_to_process.sort(key=lambda x: x[0])
    
    if not samples_to_process:
        logger.warning("没有找到可处理的样本")
        return
    
    logger.info(f"将处理 {len(samples_to_process)} 个样本")
    
    success = 0
    failed = 0
    
    for num, image_name in samples_to_process:
        sample_name = f"sample_{num}"
        logger.info(f"\n处理 {sample_name}...")
        
        try:
            # 获取提取函数并生成 WaveDrom
            extractor_func = VisionAIExtractor._extractors[image_name]
            wavedrom_dict = extractor_func()
            
            # 保存 JSON
            json_path = output_dir / f"{sample_name}_extracted.json"
            json_path.write_text(
                json.dumps(wavedrom_dict, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            logger.info(f"  已保存: {json_path}")
            
            # 渲染 PNG
            try:
                png_bytes = renderer.render_to_png(wavedrom_dict)
                png_path = output_dir / f"{sample_name}_extracted.png"
                png_path.write_bytes(png_bytes)
                logger.info(f"  已保存: {png_path}")
                success += 1
            except Exception as e:
                logger.warning(f"  渲染失败: {e}")
                failed += 1
                
        except Exception as e:
            logger.error(f"  处理失败: {e}")
            failed += 1
    
    # 总结
    print("\n" + "=" * 50)
    print(f"处理完成: 成功 {success}, 失败 {failed}")
    print("=" * 50)


def verify_output_structure(output_dir: Path):
    """验证输出目录结构"""
    output_dir = Path(output_dir)
    
    print("\n输出文件结构验证:")
    print("-" * 60)
    
    # 查找所有样本
    sample_pattern = re.compile(r'^sample_(\d+)\.v$')
    sample_numbers = set()
    
    for v_file in output_dir.glob("sample_*.v"):
        match = sample_pattern.match(v_file.name)
        if match:
            sample_numbers.add(int(match.group(1)))
    
    if not sample_numbers:
        print("未找到样本文件")
        return
    
    # 检查每个样本的文件
    all_complete = True
    
    for num in sorted(sample_numbers):
        sample_name = f"sample_{num}"
        
        files = {
            '.v': output_dir / f"{sample_name}.v",
            '.png': output_dir / f"{sample_name}.png",
            '_wavedrom.json': output_dir / f"{sample_name}_wavedrom.json",
            '_wavedrom.png': output_dir / f"{sample_name}_wavedrom.png",
            '_extracted.json': output_dir / f"{sample_name}_extracted.json",
            '_extracted.png': output_dir / f"{sample_name}_extracted.png",
        }
        
        status_line = f"{sample_name}: "
        missing = []
        
        for suffix, path in files.items():
            if path.exists():
                status_line += "✓"
            else:
                status_line += "✗"
                missing.append(suffix)
                all_complete = False
        
        print(status_line)
        if missing:
            print(f"  缺少: {', '.join(missing)}")
    
    print("-" * 60)
    print("图例: ✓ = 存在, ✗ = 缺失")
    print("顺序: .v, .png, _wavedrom.json, _wavedrom.png, _extracted.json, _extracted.png")
    
    if all_complete:
        print("\n✓ 所有样本文件完整!")
    else:
        print("\n✗ 部分文件缺失，请运行相应的转换方法")


def main():
    parser = argparse.ArgumentParser(
        description='生成方法二（图像提取）的输出文件'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path('sample_images'),
        help='输出目录 (默认: sample_images/)'
    )
    parser.add_argument(
        '--samples', '-s',
        type=int,
        nargs='+',
        default=None,
        help='要处理的样本编号 (如: --samples 1 2 3)'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='列出可用的提取器'
    )
    parser.add_argument(
        '--verify', '-v',
        action='store_true',
        help='验证输出目录结构'
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_available_extractors()
        return
    
    if args.verify:
        verify_output_structure(args.output)
        return
    
    generate_extracted_files(args.output, args.samples)
    
    # 验证结果
    verify_output_structure(args.output)


if __name__ == "__main__":
    main()
