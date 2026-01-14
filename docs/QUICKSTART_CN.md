# 快速入门指南

本指南帮助您快速上手 Verilog-WaveDrom 波形转换工具。

---

## 目录

1. [环境准备](#环境准备)
2. [快速开始](#快速开始)
3. [方法一：仿真转换](#方法一仿真转换)
4. [方法二：图像提取](#方法二图像提取)
5. [输出文件说明](#输出文件说明)
6. [常用命令](#常用命令)

---

## 环境准备

### 1. 安装 Python 依赖

```bash
pip install datasets tqdm pillow wavedrom playwright
playwright install chromium
```

### 2. 安装 Icarus Verilog (方法一需要)

```bash
# Windows (使用 Chocolatey)
choco install iverilog

# macOS
brew install icarus-verilog

# Linux (Ubuntu/Debian)
sudo apt install iverilog
```

### 3. 验证安装

```bash
python run_conversion.py --check-deps
```

预期输出:
```
检查依赖...
----------------------------------------
Python 包:
  ✓ datasets
  ✓ wavedrom
  ✓ playwright
  ✓ PIL
  ✓ tqdm

系统工具:
  ✓ iverilog
  ✓ vvp
  ✓ npx
```

---

## 快速开始

### 一键生成样本

```bash
# 从数据集提取 5 个样本，运行两种转换方法
python run_conversion.py --count 5
```

### 查看输出

```
sample_images/
├── sample_1.v              # 原始 Verilog 代码
├── sample_1.png            # 原始波形图
├── sample_1_wavedrom.json  # 方法一：仿真生成的 JSON
├── sample_1_wavedrom.png   # 方法一：仿真生成的波形图
├── sample_1_extracted.json # 方法二：图像提取的 JSON
├── sample_1_extracted.png  # 方法二：图像提取的波形图
└── ...
```

---

## 方法一：仿真转换

### 原理

```
Verilog → 解析 → 生成测试平台 → 仿真 → VCD → WaveDrom JSON → PNG
```

### 使用方法

#### 命令行

```bash
# 处理已有的 Verilog 文件
python run_conversion.py --use-existing --method1-only

# 从数据集提取并处理
python run_conversion.py --count 10 --method1-only
```

#### Python API

```python
from convert_dataset import VerilogPipeline
from pathlib import Path

# 创建流水线
pipeline = VerilogPipeline(match_original=True)

# 读取 Verilog
verilog_code = Path("sample_images/sample_1.v").read_text()

# 处理并保存
pipeline.process_to_files(
    verilog_code=verilog_code,
    output_dir=Path("sample_images"),
    sample_name="sample_1"
)
```

### 输出

- `sample_1_wavedrom.json` - WaveDrom JSON 格式
- `sample_1_wavedrom.png` - 渲染的波形图

---

## 方法二：图像提取

### 原理

```
波形图像 → [视觉分析/预定义提取器] → WaveDrom JSON → PNG
```

### 使用方法

#### 命令行

```bash
# 列出可用的提取器
python generate_method2_outputs.py --list

# 生成方法二输出
python generate_method2_outputs.py

# 处理指定样本
python generate_method2_outputs.py --samples 1 2 3
```

#### Python API

```python
from image_to_wavedrom import VisionAIExtractor
from pathlib import Path

# 使用预定义提取器
VisionAIExtractor.extract_and_render(
    image_path=Path("sample_images/sample_1.png"),
    output_dir=Path("sample_images"),
    sample_name="sample_1"
)
```

### 添加自定义提取器

```python
from image_to_wavedrom import VisionAIExtractor, create_wavedrom_json

def get_my_sample_wavedrom():
    signals = [
        {"name": "clk", "wave": "p........"},
        {"name": "data", "wave": "x.=.=.=.=", "data": ["A", "B", "C", "D"]}
    ]
    return create_wavedrom_json(signals, "My Sample")

# 注册提取器
VisionAIExtractor.register_extraction("my_sample.png", get_my_sample_wavedrom)
```

### 输出

- `sample_1_extracted.json` - 从图像提取的 WaveDrom JSON
- `sample_1_extracted.png` - 渲染的波形图

---

## 输出文件说明

### 文件结构

| 文件 | 说明 | 来源 |
|------|------|------|
| `sample_X.v` | 原始 Verilog 代码 | 数据集 |
| `sample_X.png` | 原始波形图 | 数据集 |
| `sample_X_wavedrom.json` | 方法一输出 | 仿真生成 |
| `sample_X_wavedrom.png` | 方法一渲染 | 仿真生成 |
| `sample_X_extracted.json` | 方法二输出 | 图像提取 |
| `sample_X_extracted.png` | 方法二渲染 | 图像提取 |

### WaveDrom JSON 格式

```json
{
  "signal": [
    {"name": "clk", "wave": "p........"},
    {"name": "rst", "wave": "1.0......"},
    {"name": "data[7:0]", "wave": "x.=.=.=.=", "data": ["0A", "1B", "2C", "3D"]}
  ],
  "config": {"hscale": 2},
  "head": {"text": "Timing Diagram", "tick": 0},
  "foot": {"text": "Cycle numbers", "tick": 0}
}
```

### 波形字符说明

| 字符 | 含义 | 示例 |
|------|------|------|
| `p` | 正边沿时钟 | `"wave": "p......."` |
| `n` | 负边沿时钟 | `"wave": "n......."` |
| `0` | 低电平 | `"wave": "0.1.0..."` |
| `1` | 高电平 | `"wave": "1.0.1..."` |
| `x` | 未知/无效 | `"wave": "x.=....."` |
| `z` | 高阻态 | `"wave": "0.z.0..."` |
| `=` | 总线数据值 | `"wave": "=.=.=...", "data": ["A", "B", "C"]` |
| `.` | 保持前一状态 | `"wave": "1...0..."` |

---

## 常用命令

### 基本操作

```bash
# 检查依赖
python run_conversion.py --check-deps

# 生成 5 个样本 (两种方法)
python run_conversion.py --count 5

# 仅提取原始文件
python run_conversion.py --count 10 --extract-only

# 验证文件结构
python generate_method2_outputs.py --verify
```

### 方法一

```bash
# 仅运行方法一
python run_conversion.py --count 10 --method1-only

# 处理单个 Verilog 文件
python convert_dataset.py --single sample_images/sample_1.v
```

### 方法二

```bash
# 列出可用提取器
python generate_method2_outputs.py --list

# 生成方法二输出
python generate_method2_outputs.py

# 处理指定样本
python generate_method2_outputs.py --samples 1 2 3
```

### 高级选项

```bash
# 使用固定随机种子 (可重复)
python run_conversion.py --count 20 --seed 42

# 指定样本索引
python run_conversion.py --indices 0 5 10 15 20

# 保存详细报告
python run_conversion.py --count 10 --save-report

# 详细日志
python run_conversion.py --count 5 -v
```

---

## 故障排除

### 问题：iverilog 未找到

```bash
# Windows
choco install iverilog

# 或手动下载并添加到 PATH
# https://bleyer.org/icarus/
```

### 问题：Playwright 浏览器未安装

```bash
playwright install chromium
```

### 问题：方法二没有可用的提取器

需要手动创建提取函数或集成 Vision AI。参见 [METHOD_DETAILS.md](METHOD_DETAILS.md)。

---

## 下一步

- 查看 [CONVERSION_GUIDE.md](CONVERSION_GUIDE.md) 了解完整技术文档
- 查看 [METHOD_DETAILS.md](METHOD_DETAILS.md) 了解方法实现细节
- 查看 [SIGNAL_ORDER_EXTRACTION.md](SIGNAL_ORDER_EXTRACTION.md) 了解信号顺序提取
