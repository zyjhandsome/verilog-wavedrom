# 方法详细说明

本文档详细说明两种波形转换方法的技术实现。

---

## 方法一：基于仿真的转换 (Simulation-Based)

### 1. 技术架构

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  Verilog    │───▶│   Parser     │───▶│   Module    │
│   .v File   │    │              │    │   Object    │
└─────────────┘    └──────────────┘    └──────┬──────┘
                                              │
                   ┌──────────────┐           │
                   │   Testbench  │◀──────────┘
                   │  Generator   │
                   └──────┬───────┘
                          │
                   ┌──────▼───────┐    ┌─────────────┐
                   │  Simulation  │───▶│  VCD File   │
                   │   (iverilog) │    │             │
                   └──────────────┘    └──────┬──────┘
                                              │
                   ┌──────────────┐           │
                   │   VCD to     │◀──────────┘
                   │   WaveDrom   │
                   └──────┬───────┘
                          │
                   ┌──────▼───────┐    ┌─────────────┐
                   │   WaveDrom   │───▶│  PNG Image  │
                   │   Renderer   │    │             │
                   └──────────────┘    └─────────────┘
```

### 2. 流程详解

#### 阶段 1: Verilog 解析

**文件**: `verilog_parser.py`

```python
def parse_verilog(verilog_code: str) -> VerilogModule:
    """
    解析 Verilog 代码，提取模块信息
    
    提取内容:
    - module 名称
    - input/output 端口
    - 端口位宽
    - wire/reg 信号
    """
```

**示例输入**:
```verilog
module counter(
    input clk,
    input rst,
    output reg [7:0] count
);
```

**解析结果**:
```python
VerilogModule(
    name="counter",
    ports=[
        Port(name="clk", direction="input", width=1),
        Port(name="rst", direction="input", width=1),
        Port(name="count", direction="output", width=8)
    ]
)
```

#### 阶段 2: 测试平台生成

**文件**: `testbench_generator.py`

```python
class TestbenchGenerator:
    def generate(self, module: VerilogModule) -> str:
        """
        生成自动测试平台
        
        生成内容:
        - 时钟信号 (10ns 周期)
        - 复位序列
        - 随机输入激励
        - VCD dump 命令
        """
```

**生成的测试平台结构**:
```verilog
`timescale 1ns/1ps

module counter_tb;
    // 信号声明
    reg clk;
    reg rst;
    wire [7:0] count;
    
    // 实例化被测模块
    counter dut (
        .clk(clk),
        .rst(rst),
        .count(count)
    );
    
    // 时钟生成
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end
    
    // VCD dump
    initial begin
        $dumpfile("waveform.vcd");
        $dumpvars(0, counter_tb);
    end
    
    // 激励
    initial begin
        rst = 1;
        #20 rst = 0;
        #1000 $finish;
    end
endmodule
```

#### 阶段 3: 仿真执行

**文件**: `simulation_runner.py`

```python
class SimulationRunner:
    def run(self, verilog_code: str, testbench: str) -> SimulationResult:
        """
        运行 Icarus Verilog 仿真
        
        步骤:
        1. 写入临时文件
        2. 编译: iverilog -o sim.vvp dut.v tb.v
        3. 执行: vvp sim.vvp
        4. 读取 VCD 输出
        """
```

**返回结果**:
```python
@dataclass
class SimulationResult:
    success: bool
    vcd_content: str       # VCD 文件内容
    stdout: str            # 仿真输出
    stderr: str            # 错误信息
    error_message: str     # 错误描述
```

#### 阶段 4: VCD 转 WaveDrom

**文件**: `vcd_to_wavedrom.py`

```python
class VCDParser:
    def parse(self, vcd_content: str) -> VCDData:
        """
        解析 VCD 文件
        
        解析内容:
        - $timescale: 时间单位
        - $var: 信号定义
        - #time: 时间戳
        - 值变化记录
        """

class WaveDromGenerator:
    def generate(self, vcd_data: VCDData) -> Dict[str, Any]:
        """
        生成 WaveDrom JSON
        
        转换规则:
        - 单比特信号: '0', '1', 'x', 'z'
        - 多比特信号: '=' + data 数组
        - 时钟信号: 'p' 或 'n'
        - 保持状态: '.'
        """
```

**VCD 格式示例**:
```
$timescale 1ns $end
$scope module counter_tb $end
$var wire 1 ! clk $end
$var wire 8 # count [7:0] $end
$upscope $end
$enddefinitions $end
#0
0!
b00000000 #
#5
1!
#10
0!
b00000001 #
```

**转换为 WaveDrom**:
```json
{
  "signal": [
    {"name": "clk", "wave": "p........."},
    {"name": "count[7:0]", "wave": "=.=.......", "data": ["0", "1"]}
  ],
  "config": {"hscale": 2}
}
```

#### 阶段 5: PNG 渲染

**文件**: `wavedrom_renderer.py`

```python
class WaveDromRenderer:
    def render_to_png(self, wavedrom_dict: Dict) -> bytes:
        """
        渲染 WaveDrom JSON 为 PNG
        
        渲染后端 (按优先级):
        1. wavedrom + Playwright (推荐)
        2. wavedrom + cairosvg
        3. wavedrom-cli (Node.js)
        """
```

### 3. 完整代码示例

```python
from pathlib import Path
from verilog_parser import parse_verilog
from testbench_generator import TestbenchGenerator
from simulation_runner import SimulationRunner
from vcd_to_wavedrom import vcd_to_wavedrom
from wavedrom_renderer import WaveDromRenderer
import json

# 1. 读取 Verilog
verilog_code = Path("counter.v").read_text()

# 2. 解析
module = parse_verilog(verilog_code)
print(f"模块: {module.name}, 端口: {[p.name for p in module.ports]}")

# 3. 生成测试平台
tb_gen = TestbenchGenerator()
testbench = tb_gen.generate(module)

# 4. 运行仿真
sim = SimulationRunner()
result = sim.run(verilog_code, testbench)

if result.success:
    # 5. 转换 VCD
    wavedrom_dict = vcd_to_wavedrom(
        result.vcd_content,
        io_port_names=[p.name for p in module.ports],
        port_definitions=module.ports
    )
    
    # 保存 JSON
    Path("counter_wavedrom.json").write_text(json.dumps(wavedrom_dict, indent=2))
    
    # 6. 渲染 PNG
    renderer = WaveDromRenderer()
    png_bytes = renderer.render_to_png(wavedrom_dict)
    Path("counter_wavedrom.png").write_bytes(png_bytes)
    
    print("转换完成!")
else:
    print(f"仿真失败: {result.error_message}")
```

---

## 方法二：基于图像提取的转换 (Image Extraction-Based)

### 1. 技术架构

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  Waveform   │───▶│  Signal Name │───▶│  Signal     │
│  PNG Image  │    │  Extractor   │    │  Order List │
└─────────────┘    └──────────────┘    └──────┬──────┘
                                              │
       ┌──────────────┐                       │
       │   Waveform   │◀──────────────────────┘
       │  Pattern     │
       │  Recognizer  │
       └──────┬───────┘
              │
       ┌──────▼───────┐    ┌─────────────┐
       │   WaveDrom   │───▶│  JSON File  │
       │   Generator  │    │             │
       └──────┬───────┘    └─────────────┘
              │
       ┌──────▼───────┐    ┌─────────────┐
       │   WaveDrom   │───▶│  PNG Image  │
       │   Renderer   │    │             │
       └──────────────┘    └─────────────┘
```

### 2. 流程详解

#### 阶段 1: 信号名称提取

**文件**: `signal_order_extractor.py`

```python
def extract_signal_names(image_path: Path) -> List[str]:
    """
    从波形图提取信号名称
    
    方法:
    1. 裁剪左侧信号名称区域
    2. 图像预处理 (灰度、二值化)
    3. OCR 识别文字
    4. 解析信号名称和位宽
    """
```

**信号名称模式识别**:
```python
# 常见信号名称格式
patterns = [
    r"(\w+)\[(\d+):(\d+)\]",  # data[7:0]
    r"(\w+)\[(\d+)\]",        # bit[0]
    r"(\w+)",                  # clk, rst
]
```

#### 阶段 2: 波形模式识别

**文件**: `image_to_wavedrom.py`

```python
def recognize_waveform_pattern(row_image: np.ndarray) -> Dict:
    """
    识别单行波形模式
    
    识别类型:
    1. 时钟信号: 周期性方波 → 'p'/'n'
    2. 单比特信号: 高低电平 → '0'/'1'/'x'/'z'
    3. 总线信号: 带数值标签 → '=' + data
    """
```

**波形字符映射**:

| 波形模式 | WaveDrom 字符 | 说明 |
|----------|---------------|------|
| 正边沿时钟 | `p` | 周期性 0→1→0 |
| 负边沿时钟 | `n` | 周期性 1→0→1 |
| 高电平 | `1` | 稳定高 |
| 低电平 | `0` | 稳定低 |
| 未知 | `x` | 不确定 |
| 高阻 | `z` | 三态 |
| 数据值 | `=` | 总线数据 |
| 保持 | `.` | 无变化 |

#### 阶段 3: 手动分析示例

对于复杂波形，可进行手动分析并创建提取函数：

**示例: FIFO 模块波形**

```python
# image_to_wavedrom.py

def get_sample_1_wavedrom() -> Dict[str, Any]:
    """
    sample_1.png 的精确重建
    
    视觉分析:
    ┌────────────────────────────────────────────┐
    │ clk:     ▔▂▔▂▔▂▔▂▔▂▔▂▔▂▔▂▔▂▔▂▔▂▔▂▔▂▔▂▔▂  │
    │ rst:     ▔▔▔▔▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂  │
    │ full:    ▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂  │
    │ a_full:  ▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂  │
    │ rd_en:   ▂▂▂▂▂▂▂▂▔▔▂▂▂▔▔▂▂▔▔▂▂▔▔▂▂▔▔▂▂  │
    │ dout:    ████ 24 ███ 81 ███ 9 ███ 63 ...│
    │ wr_en:   ▂▂▂▂▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▂▂▂▂  │
    │ empty:   ▔▔▔▔▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂  │
    │ din:     ████ 24 ██ 81 ██ 9 ██ 63 ...   │
    │ a_empty: ▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂▂  │
    └────────────────────────────────────────────┘
    
    转换规则:
    - ▔▂ (高低交替) → 时钟用 'p', 普通信号用 '1'/'0'
    - 稳定高 ▔▔▔ → '1...'
    - 稳定低 ▂▂▂ → '0...'
    - 数据框 ████ XX → '=' + data: ["XX"]
    """
    signals = [
        # 时钟: 连续脉冲
        {"name": "clk", "wave": "p................................"},
        
        # 复位: 初始高，然后低
        {"name": "rst", "wave": "1.0.............................."},
        
        # 状态标志: 始终低
        {"name": "full", "wave": "0................................"},
        {"name": "a_full", "wave": "0................................"},
        
        # 读使能: 间歇脉冲
        {"name": "rd_en", "wave": "0........1..0.1..0.1..0.1..0.1..0"},
        
        # 数据输出: 读取时变化
        {"name": "dout[7:0]", "wave": "x........=..=.=..=.=..=.=..=.=..=", 
         "data": ["24", "81", "9", "63", "D", "8D", "65", "12", "1", "D"]},
        
        # 写使能: 写入期间高
        {"name": "wr_en", "wave": "0..1..1..1..1..1..1..1..1..1..1..0"},
        
        # 空标志: 初始高，写入后低
        {"name": "empty", "wave": "1..0............................."},
        
        # 数据输入: 连续数据
        {"name": "din[7:0]", 
         "wave": "x..=..=..=..=..=..=..=..=..=..=..=..=..=..=..=..=..=..=..=",
         "data": ["24", "81", "9", "63", "D", "8D", "65", "12", "1", "D", 
                  "76", "3D", "ED", "8C", "F9", "C6", "C5", "AA", "E5"]},
        
        # 近空标志: 始终低
        {"name": "a_empty", "wave": "0................................"}
    ]
    
    return {
        "signal": signals,
        "config": {"hscale": 2},
        "head": {"text": "FIFO Timing Diagram", "tick": 0},
        "foot": {"text": "Cycle numbers", "tick": 0}
    }
```

#### 阶段 4: Vision AI 集成 (高级)

**Prompt 模板**:

```python
EXTRACTION_PROMPT = """
分析此波形图像，提取 WaveDrom JSON 表示。

步骤:
1. 识别左侧信号名称（从上到下）
2. 分析每个信号的波形模式:
   - 时钟 (方波): 使用 'p'
   - 单比特: 使用 '0', '1', 'x', '.'
   - 总线: 使用 '=' 配合 data 数组

3. 读取总线信号的十六进制值
4. 计算时钟周期数
5. 保持信号顺序与图像一致

输出 JSON 格式:
{
  "signal": [
    {"name": "clk", "wave": "p...."},
    {"name": "data[7:0]", "wave": "x.=.=", "data": ["A0", "B1"]}
  ]
}
"""
```

**集成示例** (使用 Claude API):

```python
import anthropic

def extract_with_vision_ai(image_path: Path) -> Dict:
    client = anthropic.Client()
    
    # 读取图像
    import base64
    image_data = base64.b64encode(image_path.read_bytes()).decode()
    
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_data
                    }
                },
                {
                    "type": "text",
                    "text": EXTRACTION_PROMPT
                }
            ]
        }]
    )
    
    # 解析返回的 JSON
    import json
    wavedrom_json = json.loads(response.content[0].text)
    return wavedrom_json
```

### 3. 完整代码示例

```python
from pathlib import Path
from image_to_wavedrom import VisionAIExtractor, create_wavedrom_json
from wavedrom_renderer import WaveDromRenderer
import json

# 方式 1: 使用预定义提取器
image_path = Path("sample_images/sample_1.png")

try:
    wavedrom_dict = VisionAIExtractor.extract_from_image(image_path)
    print("使用预定义提取器成功!")
except ValueError:
    print("没有预定义提取器，需要手动分析或使用 Vision AI")

# 方式 2: 手动创建 WaveDrom
signals = [
    {"name": "clk", "wave": "p........"},
    {"name": "rst", "wave": "1.0......"},
    {"name": "data[7:0]", "wave": "x.=.=.=.=", "data": ["00", "11", "22", "33"]}
]
wavedrom_dict = create_wavedrom_json(signals, "My Timing Diagram")

# 保存 JSON
Path("output.json").write_text(json.dumps(wavedrom_dict, indent=2))

# 渲染 PNG
renderer = WaveDromRenderer()
png_bytes = renderer.render_to_png(wavedrom_dict)
Path("output.png").write_bytes(png_bytes)

print("转换完成!")
```

### 4. 注册自定义提取器

```python
from image_to_wavedrom import VisionAIExtractor, create_wavedrom_json

def my_custom_extractor():
    """自定义样本的波形提取"""
    signals = [
        {"name": "clk", "wave": "p.........."},
        {"name": "enable", "wave": "0..1......."},
        {"name": "addr[15:0]", "wave": "x..=.=.=...", "data": ["0000", "1234", "5678"]}
    ]
    return create_wavedrom_json(signals, "Custom Sample")

# 注册到提取器
VisionAIExtractor.register_extraction("my_sample.png", my_custom_extractor)

# 现在可以使用了
result = VisionAIExtractor.extract_from_image(Path("my_sample.png"))
```

---

## 方法比较

| 特性 | 方法一 (仿真) | 方法二 (图像提取) |
|------|---------------|-------------------|
| 自动化程度 | 高 | 低 (需预定义或 AI) |
| 准确性 | 取决于仿真激励 | 可精确匹配原图 |
| 依赖 | Icarus Verilog | OCR / Vision AI |
| 处理速度 | 较慢 (需仿真) | 较快 |
| 扩展性 | 通用 | 需逐个定义 |
| 最佳场景 | 批量自动化处理 | 精确复现特定波形 |

---

## 故障排除

### 方法一常见问题

**问题: iverilog 编译失败**
```
解决: 
1. 检查 Verilog 语法
2. 确保所有模块文件都在同一目录
3. 查看 stderr 输出的具体错误
```

**问题: VCD 文件为空**
```
解决:
1. 确保测试平台包含 $dumpfile/$dumpvars
2. 检查仿真是否正常结束
3. 增加仿真时间
```

**问题: 波形信号顺序不对**
```
解决:
1. 使用 signal_order_extractor 重新排序
2. 传入 original_image_path 参数
3. 设置 match_original=True
```

### 方法二常见问题

**问题: 没有预定义提取器**
```
解决:
1. 手动分析波形图并创建提取函数
2. 使用 VisionAIExtractor.register_extraction() 注册
3. 考虑集成 Vision AI
```

**问题: 提取的数据不准确**
```
解决:
1. 检查波形字符是否正确 (参考 WaveDrom 文档)
2. 验证 data 数组与 '=' 字符数量匹配
3. 确保信号顺序与原图一致
```
