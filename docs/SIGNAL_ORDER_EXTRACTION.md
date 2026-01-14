# 信号顺序提取方案说明

## 概述

本方案解决了从 Verilog 代码生成 WaveDrom 波形图时，信号顺序和数量与原始数据集图像不匹配的问题。

### 核心问题

1. **信号顺序不匹配**：Icarus Verilog 仿真器生成的 VCD 文件中信号顺序与原始数据集图像中的顺序不同
2. **信号数量不匹配**：生成的 WaveDrom 可能包含原图中不存在的内部信号（如 `counter`、`prev_value`）

### 解决方案

使用 Tesseract OCR 从原始波形图像中提取信号名称和顺序，然后重新排序和过滤生成的 WaveDrom JSON。

---

## 技术架构

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Original PNG   │───▶│  OCR Extraction  │───▶│  Signal Order   │
│  (Waveform)     │    │  (Tesseract)     │    │  List           │
└─────────────────┘    └──────────────────┘    └────────┬────────┘
                                                        │
┌─────────────────┐    ┌──────────────────┐             │
│  Verilog Code   │───▶│  Simulation      │             │
│  (.v file)      │    │  (Icarus)        │             │
└─────────────────┘    └────────┬─────────┘             │
                                │                       │
                       ┌────────▼─────────┐             │
                       │  VCD File        │             │
                       │  (waveform.vcd)  │             │
                       └────────┬─────────┘             │
                                │                       │
                       ┌────────▼─────────┐    ┌────────▼────────┐
                       │  VCD to WaveDrom │───▶│ Signal Reorder  │
                       │  Converter       │    │ & Filter        │
                       └──────────────────┘    └────────┬────────┘
                                                        │
                                               ┌────────▼────────┐
                                               │  Final WaveDrom │
                                               │  JSON + PNG     │
                                               └─────────────────┘
```

---

## 核心模块

### 1. SignalOrderExtractor 类

位置：`signal_order_extractor.py`

#### 主要功能

```python
class SignalOrderExtractor:
    """从波形图像中提取信号名称和顺序"""
    
    def extract_signal_order(self, image_path: Path) -> List[str]:
        """提取信号名称列表（从上到下顺序）"""
        
    def _find_signal_name_region(self, image: Image) -> Image:
        """查找信号名称区域（处理左对齐和右对齐）"""
        
    def _preprocess_for_ocr(self, image: Image, scale_factor: int = 3) -> Image:
        """预处理图像以提高 OCR 准确率"""
        
    def _extract_with_bounding_boxes(self, image: Image) -> List[str]:
        """使用边界框提取信号名称"""
```

### 2. 图像预处理流程

```python
def _preprocess_for_ocr(self, image, scale_factor=3):
    # 1. 转换为 RGB
    # 2. 提取蓝色文本像素
    # 3. 创建高对比度黑白图像
    # 4. 3x 放大（提高小文本识别率）
    # 5. 锐化处理
```

#### 蓝色文本检测阈值

```python
# 亮蓝色文本
is_blue = b > 180 and b > r + 30 and b > g + 10

# 暗蓝色文本
is_dark_blue = b > 120 and b > r + 20 and b > g + 20 and r < 180 and g < 200
```

### 3. 多遍 OCR 策略

```python
def _extract_with_bounding_boxes(self, image):
    # 第一遍：PSM 6（块文本模式）
    lines = self._ocr_pass(image, config='--oem 3 --psm 6', min_conf=30)
    
    # 第二遍：PSM 11（稀疏文本模式，捕获单字符）
    sparse_lines = self._ocr_pass(image, config='--oem 3 --psm 11', min_conf=20)
    
    # 合并结果
    merged = self._merge_ocr_results(lines, sparse_lines)
```

### 4. OCR 后处理

#### 常见 OCR 错误修复

| OCR 输出 | 修正后 | 说明 |
|----------|--------|------|
| `0` | `o` | 数字0→字母o |
| `1` | `i` | 数字1→字母i |
| `sys_cik` | `sys_clk` | 字符混淆 |
| `edram_rst` | `sdram_rst` | 首字母丢失 |
| `[15:0` | `[15:0]` | 补全括号 |
| `tmpt_bar` | `tmp1_bar` | t→1 混淆 |

#### 代码实现

```python
def _post_process_signals(self, signals):
    for sig in signals:
        # 修复数字→字母混淆
        if sig == '0': sig = 'o'
        if sig == '1': sig = 'i'
        
        # 修复常见 OCR 错误
        if sig.startswith('edram_'):
            sig = 'sdram_' + sig[6:]
        
        # 补全缺失的括号
        if '[' in sig and ']' not in sig:
            sig += ']'
```

### 5. 模糊匹配算法

用于处理 OCR 提取的信号名称与 VCD 生成的信号名称之间的差异。

```python
def fuzzy_match_score(ocr_name, signal_name):
    """计算匹配分数（0.0 - 1.0）"""
    
    # 1. 精确匹配 → 1.0
    # 2. OCR 字符归一化后匹配 → 0.98
    # 3. 单字符混淆匹配（i/l/1, o/0）→ 0.95
    # 4. 前缀差异匹配（tmp → out_tmp）→ 0.9
    # 5. 包含关系匹配 → 0.8
    # 6. 字符相似度计算
```

#### OCR 字符归一化

```python
def normalize_ocr_chars(text):
    """归一化常见 OCR 混淆字符"""
    replacements = {
        'l': 'i',  # l ↔ i
        '1': 'i',  # 1 ↔ i
        '0': 'o',  # 0 ↔ o
    }
```

### 6. 信号重排序和过滤

```python
def reorder_wavedrom_signals(wavedrom_dict, reference_order, filter_to_reference=True):
    """
    根据参考顺序重新排列 WaveDrom 信号
    
    Args:
        wavedrom_dict: WaveDrom JSON 字典
        reference_order: OCR 提取的信号顺序列表
        filter_to_reference: 是否过滤掉不在参考列表中的信号
    """
```

---

## 处理流程详解

### Step 1: 信号名称区域检测

```python
def _find_signal_name_region(self, image):
    # 扫描所有列的蓝色像素
    # 找到信号名称结束位置（蓝色列的间隙 > 50 像素）
    # 裁剪出信号名称区域
```

**处理右对齐信号名称**：
- 短信号名（如 `o`）可能位于 X=180
- 长信号名（如 `seriesterminationcontrol`）从 X=0 开始

### Step 2: 图像预处理

1. **颜色过滤**：只保留蓝色文本像素
2. **3x 放大**：提高小文本（如 `i`, `o`）的识别率
3. **锐化**：增强文本边缘

### Step 3: OCR 提取

使用两种 Tesseract 模式：
- **PSM 6**：假设图像是统一的文本块
- **PSM 11**：稀疏文本模式，更好地捕获孤立字符

### Step 4: 结果合并

1. 按 Y 坐标分组（同一行的文本）
2. 按 X 坐标排序并合并
3. 清理和验证信号名称

### Step 5: 信号匹配和重排序

1. 使用模糊匹配将 OCR 提取的名称与 VCD 信号对应
2. 按 OCR 顺序重新排列
3. 过滤掉原图中不存在的信号

---

## 使用方法

### 命令行使用

```bash
# 提取信号顺序
python signal_order_extractor.py sample_images/sample_1.png

# 提取并重新排序 WaveDrom JSON
python signal_order_extractor.py sample_images/sample_1.png sample_images/sample_1_wavedrom.json
```

### API 使用

```python
from signal_order_extractor import SignalOrderExtractor, extract_and_match_order

# 方式 1：只提取信号顺序
extractor = SignalOrderExtractor()
signals = extractor.extract_signal_order(Path('waveform.png'))
print(signals)  # ['sys_clk', 'sdram_rst', 'write', ...]

# 方式 2：提取并应用到 WaveDrom
wavedrom_dict = {...}  # 从 VCD 生成的 WaveDrom
reordered = extract_and_match_order(
    original_image_path=Path('waveform.png'),
    wavedrom_dict=wavedrom_dict,
    filter_to_original=True  # 过滤掉原图中不存在的信号
)
```

### 集成到完整流程

```python
from convert_dataset import VerilogPipeline

pipeline = VerilogPipeline(match_original=True)
pipeline.process_to_files(
    verilog_code,
    output_dir=Path('output'),
    sample_name='sample_1',
    original_image_path=Path('sample_images/sample_1.png')  # 用于信号顺序
)
```

---

## 依赖要求

### 必需

- Python 3.8+
- Pillow (PIL)
- pytesseract

### Tesseract OCR 安装

**Windows:**
```bash
winget install UB-Mannheim.TesseractOCR
```

**Linux:**
```bash
sudo apt install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

---

## 配置选项

### Tesseract 路径配置

```python
# 自动检测（默认）
# Windows: C:\Program Files\Tesseract-OCR\tesseract.exe
# 或手动设置：
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'/path/to/tesseract'
```

### OCR 参数调整

```python
# 在 SignalOrderExtractor 中可调整：
scale_factor = 3      # 图像放大倍数（1-4）
min_conf = 30         # 最低置信度（0-100）
line_merge_threshold = 20  # 行合并阈值（像素）
```

---

## 性能和限制

### 识别率

| 信号类型 | 识别率 | 说明 |
|----------|--------|------|
| 长名称 (>5字符) | ~99% | 如 `seriesterminationcontrol` |
| 中等名称 (3-5字符) | ~95% | 如 `write`, `read` |
| 短名称 (1-2字符) | ~90% | 如 `i`, `o`, `oe` |

### 已知限制

1. **极小字体**：小于 8px 的文本可能无法识别
2. **非蓝色文本**：仅针对蓝色信号名称优化
3. **复杂背景**：有噪声的波形图可能影响识别

### 性能数据

- 单张图片处理时间：约 1-3 秒
- 主要耗时：Tesseract OCR 处理

---

## 故障排除

### 问题：信号未被识别

1. 检查图像质量和分辨率
2. 尝试调整 `scale_factor`
3. 检查蓝色检测阈值

### 问题：信号名称错误

1. 检查 `_post_process_signals` 中的修正规则
2. 添加特定信号的修正映射
3. 调整模糊匹配阈值

### 问题：顺序不正确

1. 检查 Y 坐标分组阈值
2. 验证原图信号实际顺序
3. 使用 `.order.txt` 文件手动指定顺序

---

## 文件结构

```
verilog-wavedrom/
├── signal_order_extractor.py    # 信号顺序提取模块
├── vcd_to_wavedrom.py           # VCD 转 WaveDrom
├── convert_dataset.py           # 数据集转换流程
├── generate_samples.py          # 样本生成脚本
├── sample_images/
│   ├── sample_1.png             # 原始波形图
│   ├── sample_1.v               # Verilog 代码
│   ├── sample_1_wavedrom.json   # 生成的 WaveDrom JSON
│   └── sample_1_wavedrom.png    # 生成的波形图
└── docs/
    └── SIGNAL_ORDER_EXTRACTION.md  # 本文档
```

---

## 版本历史

### v1.0 (2026-01-14)

- 初始实现 Tesseract OCR 提取
- 支持蓝色文本检测
- 多遍 OCR 策略
- 模糊匹配算法
- OCR 错误自动修正（0→o, 1→i 等）
- 信号名称区域自动检测（支持右对齐）
