# Verilog-WaveDrom 波形转换工具

将 Verilog 代码和波形图转换为 WaveDrom JSON 格式的完整解决方案。

## 快速开始

### 1. 安装依赖

```bash
# Python 依赖
pip install datasets tqdm pillow wavedrom playwright
playwright install chromium

# Icarus Verilog (方法一需要)
# Windows: choco install iverilog
# macOS: brew install icarus-verilog
# Linux: sudo apt install iverilog
```

### 2. 检查依赖

```bash
python run_conversion.py --check-deps
```

### 3. 运行转换

```bash
# 生成 5 个样本（两种方法）
python run_conversion.py --count 5

# 仅运行方法一（仿真）
python run_conversion.py --count 10 --method1-only

# 仅运行方法二（图像提取）
python run_conversion.py --count 5 --method2-only
```

## 输出文件结构

```
sample_images/
├── sample_1.v              # 原始 Verilog 代码
├── sample_1.png            # 原始波形图（从数据集提取）
├── sample_1_wavedrom.json  # 方法一：仿真生成的 WaveDrom JSON
├── sample_1_wavedrom.png   # 方法一：仿真生成的波形图
├── sample_1_extracted.json # 方法二：图像提取的 WaveDrom JSON
├── sample_1_extracted.png  # 方法二：图像提取后渲染的波形图
└── ...
```

## 两种转换方法

### 方法一：基于仿真的转换 (Simulation-Based)

```
Verilog Code → Parse → Testbench → Simulate → VCD → WaveDrom JSON → PNG
```

**优点：**
- 完全自动化
- 波形数据准确
- 支持所有 Verilog 模块

**缺点：**
- 需要安装 Icarus Verilog
- 仿真激励与原图可能不同
- 处理时间较长

### 方法二：基于图像提取的转换 (Image Extraction-Based)

```
Waveform Image → [Vision AI / Manual Analysis] → WaveDrom JSON → PNG
```

**优点：**
- 可精确匹配原始波形
- 无需仿真环境

**缺点：**
- 需要预定义提取器或 Vision AI
- 目前仅支持少数预定义样本

## 命令行参数

```
python run_conversion.py [选项]

选项:
  --count, -n N         处理样本数量 (默认: 5)
  --output, -o DIR      输出目录 (默认: sample_images/)
  --data-dir DIR        parquet 数据目录
  --seed N              随机种子 (可重复选择)
  --indices I1 I2 ...   指定样本索引
  --extract-only        仅提取原始文件
  --method1-only        仅运行方法一 (仿真)
  --method2-only        仅运行方法二 (图像提取)
  --use-existing        对已有文件运行转换
  --check-deps          检查依赖并退出
  --save-report         保存 JSON 报告
  --verbose, -v         详细日志
```

## 使用示例

### 批量处理

```bash
# 生成 20 个样本，使用固定种子
python run_conversion.py --count 20 --seed 42

# 仅提取原始文件
python run_conversion.py --count 50 --extract-only

# 对已提取的文件运行转换
python run_conversion.py --use-existing --method1-only
```

### 指定样本

```bash
# 处理特定索引的样本
python run_conversion.py --indices 0 5 10 15 20
```

### 保存报告

```bash
# 保存 JSON 格式的转换报告
python run_conversion.py --count 10 --save-report
```

## Python API

```python
from run_conversion import UnifiedConverter

# 创建转换器
converter = UnifiedConverter(
    output_dir=Path("my_output"),
    match_original=True
)

# 批量转换
report = converter.convert_samples(
    count=10,
    seed=42,
    run_method1=True,
    run_method2=False
)

print(report.summary())
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `run_conversion.py` | **统一入口** - 推荐使用 |
| `generate_samples.py` | 样本生成脚本 |
| `convert_dataset.py` | 方法一：仿真转换流水线 |
| `image_to_wavedrom.py` | 方法二：图像提取转换 |
| `verilog_parser.py` | Verilog 代码解析器 |
| `testbench_generator.py` | 测试平台生成器 |
| `simulation_runner.py` | 仿真运行器 |
| `vcd_to_wavedrom.py` | VCD 转 WaveDrom |
| `wavedrom_renderer.py` | WaveDrom PNG 渲染器 |
| `signal_order_extractor.py` | 信号顺序提取 |
| `config.py` | 配置文件 |
| `validate_samples.py` | 样本验证工具 |

## 详细文档

查看 [docs/CONVERSION_GUIDE.md](docs/CONVERSION_GUIDE.md) 获取完整的技术文档。

## 许可证

MIT License
