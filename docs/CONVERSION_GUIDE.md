# Verilog 波形图到 WaveDrom 转换方案

## 项目概述

本项目提供从 Verilog 代码和波形图转换为 WaveDrom JSON 格式的完整解决方案。支持两种转换方法：

- **方法一 (Simulation)**: 基于仿真的转换 - 通过 Verilog 仿真生成 VCD，再转换为 WaveDrom
- **方法二 (Extraction)**: 基于图像提取的转换 - 从原始波形图像直接提取 WaveDrom

---

## 数据集结构

### 输入数据
```
verilog-wavedrom/data/
├── train-00000-of-00024.parquet  # 训练集 (24个分片)
├── train-00001-of-00024.parquet
├── ...
├── test-00000-of-00005.parquet   # 测试集 (5个分片)
├── ...
```

### Parquet 数据集字段
| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | string | Verilog 源代码 |
| `image` | bytes/PIL.Image | 原始波形图像 |

### 输出文件结构
```
sample_images/
├── sample_1.v              # 原始 Verilog 代码
├── sample_1.png            # 原始波形图（从数据集提取）
├── sample_1_wavedrom.json  # 方法一输出：仿真生成的 WaveDrom JSON
├── sample_1_wavedrom.png   # 方法一渲染：仿真生成的波形图
├── sample_1_extracted.json # 方法二输出：图像提取的 WaveDrom JSON
├── sample_1_extracted.png  # 方法二渲染：图像提取后渲染的波形图
├── sample_2.v
├── sample_2.png
├── sample_2_wavedrom.json
├── sample_2_wavedrom.png
├── sample_2_extracted.json
├── sample_2_extracted.png
└── ...
```

---

## 方法一：基于仿真的转换 (Simulation-Based)

### 原理
```
Verilog Code → Parse → Generate Testbench → Simulate (Icarus Verilog) 
    → VCD File → Parse VCD → Generate WaveDrom JSON → Render PNG
```

### 技术流程

#### 1. Verilog 解析 (`verilog_parser.py`)
- 解析模块定义、端口声明
- 提取输入/输出端口及位宽
- 识别时钟和复位信号

#### 2. 测试平台生成 (`testbench_generator.py`)
- 自动生成激励信号
- 时钟信号驱动
- 复位序列
- 随机输入激励

#### 3. 仿真执行 (`simulation_runner.py`)
- 使用 Icarus Verilog (iverilog) 编译
- 运行仿真生成 VCD 文件
- 捕获仿真输出

#### 4. VCD 转换 (`vcd_to_wavedrom.py`)
- 解析 VCD 时序数据
- 提取信号变化
- 生成 WaveDrom JSON 格式

#### 5. PNG 渲染 (`wavedrom_renderer.py`)
- 支持多种渲染后端：
  - Python wavedrom + Playwright
  - Python wavedrom + cairosvg
  - wavedrom-cli (Node.js)

### 核心类和函数

```python
# convert_dataset.py
class VerilogPipeline:
    """完整的 Verilog 到 WaveDrom 转换流水线"""
    
    def process(self, verilog_code: str, index: int = 0, 
                original_image_path: Path = None) -> Optional[ProcessedSample]:
        """
        处理单个 Verilog 样本
        
        Args:
            verilog_code: Verilog 源代码
            index: 样本索引（用于日志）
            original_image_path: 原始波形图路径（用于信号排序）
            
        Returns:
            ProcessedSample 包含:
            - verilog_code: 原始代码
            - wavedrom_json: 生成的 JSON
            - waveform_image: PNG 字节
            - module_name: 模块名
        """
    
    def process_to_files(self, verilog_code: str, output_dir: Path, 
                         sample_name: str, original_image_path: Path = None) -> bool:
        """
        处理并保存到文件
        
        输出:
            - {sample_name}_wavedrom.json
            - {sample_name}_wavedrom.png
        """
```

### 使用示例

```python
from convert_dataset import VerilogPipeline
from pathlib import Path

# 创建流水线
pipeline = VerilogPipeline(match_original=True)

# 读取 Verilog 代码
verilog_code = Path("sample_1.v").read_text()

# 处理并保存
success = pipeline.process_to_files(
    verilog_code=verilog_code,
    output_dir=Path("sample_images"),
    sample_name="sample_1",
    original_image_path=Path("sample_images/sample_1.png")
)

if success:
    print("方法一转换成功!")
```

### 命令行使用

```bash
# 处理单个 Verilog 文件
python convert_dataset.py --single sample_images/sample_1.v

# 处理数据集子集
python convert_dataset.py --subset 10

# 检查依赖
python convert_dataset.py --check-deps
```

---

## 方法二：基于图像提取的转换 (Image Extraction-Based)

### 原理
```
Waveform Image → [Vision AI / Image Analysis] → Extract Signal Names 
    → Extract Waveform Patterns → Generate WaveDrom JSON → Render PNG
```

### 技术流程

#### 1. 信号名称提取 (`signal_order_extractor.py`)
- OCR 识别图像中的信号名称
- 识别信号顺序和层级结构

#### 2. 波形模式识别 (`image_to_wavedrom.py`)
- 时钟信号识别（方波模式）
- 单比特信号识别（高/低电平）
- 总线信号识别（十六进制数值）

#### 3. WaveDrom 生成
- 构建 WaveDrom JSON 结构
- 信号排序匹配原图

### 核心类和函数

```python
# image_to_wavedrom.py
class VisionAIExtractor:
    """使用视觉 AI 从图像提取波形数据"""
    
    EXTRACTION_PROMPT = """
    分析波形图像并提取 WaveDrom JSON 表示:
    1. 读取左侧信号名称
    2. 分析波形模式：
       - 时钟信号: 使用 'p' 表示正边沿时钟
       - 单比特信号: 使用 '0', '1', 'x' 表示状态
       - 总线信号: 使用 '=' 表示值变化，data 数组存储十六进制值
    3. 计算时钟周期数
    4. 读取所有总线信号的十六进制值
    """
    
    @staticmethod
    def extract_from_image(image_path: Path, verilog_code: str = None) -> Dict[str, Any]:
        """从图像提取 WaveDrom JSON"""
    
    @staticmethod
    def extract_and_render(image_path: Path, output_dir: Path, 
                           sample_name: str) -> bool:
        """
        提取并渲染到文件
        
        输出:
            - {sample_name}_extracted.json
            - {sample_name}_extracted.png
        """
```

### 预定义提取器

对于已分析的样本，提供精确的手动提取函数：

```python
# image_to_wavedrom.py

def get_sample_1_wavedrom() -> Dict[str, Any]:
    """
    FIFO 模块波形精确重建
    
    信号分析:
    - clk: 连续时钟脉冲
    - rst: 前2个周期高，然后低
    - full/a_full: 始终为低
    - rd_en: 读使能脉冲
    - dout[7:0]: 读取数据输出
    - wr_en: 写使能脉冲
    - empty: 初始高，写入后变低
    - din[7:0]: 写入数据
    - a_empty: 始终为低
    """
    signals = [
        {"name": "clk", "wave": "p................................"},
        {"name": "rst", "wave": "1.0.............................."},
        {"name": "full", "wave": "0................................"},
        # ... 更多信号
    ]
    return create_wavedrom_json(signals, "FIFO Timing Diagram")
```

### 使用示例

```python
from image_to_wavedrom import VisionAIExtractor
from pathlib import Path

# 提取并渲染
success = VisionAIExtractor.extract_and_render(
    image_path=Path("sample_images/sample_1.png"),
    output_dir=Path("sample_images"),
    sample_name="sample_1"
)

if success:
    print("方法二转换成功!")
```

### 命令行使用

```bash
# 处理单个图像
python image_to_wavedrom.py --image sample_images/sample_1.png --render

# 处理目录中所有样本
python image_to_wavedrom.py --process-samples sample_images/

# 重新生成所有预定义样本
python image_to_wavedrom.py --recreate-all
```

### 扩展 Vision AI 提取

要支持更多样本，可以注册自定义提取器：

```python
from image_to_wavedrom import VisionAIExtractor, create_wavedrom_json

def get_sample_4_wavedrom():
    signals = [
        {"name": "clk", "wave": "p........"},
        {"name": "data", "wave": "x.=.=.=.=", "data": ["A", "B", "C", "D"]},
    ]
    return create_wavedrom_json(signals, "Sample 4")

# 注册提取器
VisionAIExtractor.register_extraction("sample_4.png", get_sample_4_wavedrom)
```

---

## 完整工作流程

### 使用 `generate_samples.py` 统一处理

```python
# generate_samples.py
class SampleGenerator:
    """从 parquet 数据集生成完整样本文件集"""
    
    def generate(self, count: int, seed: int = None,
                 extract_only: bool = False,
                 method1_only: bool = False,
                 method2_only: bool = False) -> GenerationStats:
        """
        生成完整样本文件集
        
        流程:
        1. 从 parquet 加载样本
        2. 提取原始文件 (.v 和 .png)
        3. 运行方法一（仿真）
        4. 运行方法二（图像提取）
        """
```

### 命令行使用

```bash
# 生成 5 个完整样本（两种方法）
python generate_samples.py --count 5

# 仅提取原始文件
python generate_samples.py --count 10 --extract-only

# 仅运行方法一
python generate_samples.py --count 5 --method1-only

# 仅运行方法二
python generate_samples.py --count 5 --method2-only

# 对已提取的文件运行方法
python generate_samples.py --use-existing --method1-only

# 使用固定随机种子（可重复）
python generate_samples.py --count 10 --seed 42

# 详细日志
python generate_samples.py --count 5 -v
```

---

## WaveDrom JSON 格式说明

### 基本结构

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

| 字符 | 含义 |
|------|------|
| `p` | 正边沿时钟 |
| `n` | 负边沿时钟 |
| `0` | 低电平 |
| `1` | 高电平 |
| `x` | 未知/无效 |
| `z` | 高阻态 |
| `=` | 总线数据值 |
| `.` | 保持前一状态 |

### 总线信号示例

```json
{
  "name": "addr[15:0]",
  "wave": "x.=.=.=...",
  "data": ["0000", "1234", "5678"]
}
```

---

## 依赖安装

### Python 依赖

```bash
pip install datasets tqdm pillow wavedrom playwright
playwright install chromium

# 可选：cairosvg 后端
pip install cairosvg
```

### 系统依赖

```bash
# Windows (使用 Chocolatey)
choco install iverilog

# macOS
brew install icarus-verilog

# Linux (Ubuntu/Debian)
sudo apt install iverilog
```

### 验证安装

```bash
python convert_dataset.py --check-deps
```

预期输出:
```
Checking dependencies...
  wavedrom-cli: OK
  wavedrom-py: OK
  playwright: OK
  cairosvg: OK
  iverilog: OK
  vvp: OK
```

---

## 配置选项

### `config.py` 配置

```python
# 目录设置
DATA_DIR = Path("verilog-wavedrom/data")  # 输入数据目录
OUTPUT_DIR = Path("output")                # 输出目录

# 处理设置
SUBSET_SIZE = 100     # 处理样本数量 (0=全部)
MAX_SIGNALS = 20      # 最大信号数量
MAX_TIME_STEPS = 50   # 最大时间步数

# 信号优先级排序
SIGNAL_PRIORITY = ['clk', 'clock', 'rst', 'reset', 'en', 'enable']

# WaveDrom 配置
WAVEDROM_CONFIG = {"hscale": 2}
WAVEDROM_HEAD = {"text": "Timing Diagram", "tick": 0}
WAVEDROM_FOOT = {"text": "Cycle numbers", "tick": 0}

# 仿真设置
SIMULATION_TIMEOUT = 30  # 秒
VCD_DUMP_TIME = 1000     # 仿真时间单位
```

---

## 常见问题

### Q: 方法一仿真失败怎么办？
A: 检查以下几点：
1. 确保 `iverilog` 和 `vvp` 已安装并在 PATH 中
2. 检查 Verilog 代码语法是否正确
3. 查看仿真错误日志

### Q: 方法二图像提取不准确怎么办？
A: 目前方法二依赖预定义的提取函数。要支持新样本：
1. 手动分析波形图
2. 创建对应的提取函数
3. 注册到 `VisionAIExtractor`

### Q: 如何提高转换速度？
A: 
1. 减少 `MAX_SIGNALS` 和 `MAX_TIME_STEPS`
2. 使用 `--method1-only` 或 `--method2-only` 只运行一种方法
3. 使用 `--use-existing` 跳过文件提取步骤

### Q: 输出的波形图与原图不一致？
A: 这可能是因为：
1. 信号顺序不同 - 可通过 `signal_order_extractor.py` 调整
2. 时间刻度不同 - 调整 `MAX_TIME_STEPS`
3. 仿真激励不同 - 测试平台生成的激励是随机的

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `generate_samples.py` | 主入口：生成完整样本文件集 |
| `convert_dataset.py` | 方法一：仿真转换流水线 |
| `image_to_wavedrom.py` | 方法二：图像提取转换 |
| `verilog_parser.py` | Verilog 代码解析器 |
| `testbench_generator.py` | 测试平台生成器 |
| `simulation_runner.py` | 仿真运行器 |
| `vcd_to_wavedrom.py` | VCD 转 WaveDrom |
| `wavedrom_renderer.py` | WaveDrom 渲染器 |
| `signal_order_extractor.py` | 信号顺序提取 |
| `config.py` | 配置文件 |
| `validate_samples.py` | 样本验证工具 |

---

## 版本历史

- v1.0 - 初始版本
  - 支持方法一（仿真转换）
  - 支持方法二（图像提取，预定义样本）
  - 支持批量处理 parquet 数据集
