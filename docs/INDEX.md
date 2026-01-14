# 文档索引

## 快速入门

| 文档 | 说明 |
|------|------|
| [QUICKSTART_CN.md](QUICKSTART_CN.md) | 🇨🇳 中文快速入门指南 |
| [../README.md](../README.md) | 项目主 README |

## 技术文档

| 文档 | 说明 |
|------|------|
| [CONVERSION_GUIDE.md](CONVERSION_GUIDE.md) | 完整转换方案和使用指南 |
| [METHOD_DETAILS.md](METHOD_DETAILS.md) | 两种方法的详细技术实现 |
| [SIGNAL_ORDER_EXTRACTION.md](SIGNAL_ORDER_EXTRACTION.md) | 信号顺序提取算法 |

## 文档结构

```
docs/
├── INDEX.md               # 本文件 - 文档索引
├── QUICKSTART_CN.md       # 中文快速入门
├── CONVERSION_GUIDE.md    # 完整转换指南
├── METHOD_DETAILS.md      # 方法详细说明
└── SIGNAL_ORDER_EXTRACTION.md  # 信号顺序提取
```

## 主要脚本

| 脚本 | 说明 | 用法 |
|------|------|------|
| `run_conversion.py` | **统一入口** - 推荐使用 | `python run_conversion.py --count 5` |
| `generate_samples.py` | 样本生成 | `python generate_samples.py -n 10` |
| `generate_method2_outputs.py` | 方法二输出生成 | `python generate_method2_outputs.py` |
| `convert_dataset.py` | 方法一流水线 | `python convert_dataset.py --single file.v` |
| `image_to_wavedrom.py` | 方法二提取器 | `python image_to_wavedrom.py --image file.png` |
| `validate_samples.py` | 样本验证 | `python validate_samples.py` |

## 快速命令

```bash
# 检查依赖
python run_conversion.py --check-deps

# 生成样本 (两种方法)
python run_conversion.py --count 5

# 仅方法一
python run_conversion.py --count 10 --method1-only

# 仅方法二
python generate_method2_outputs.py

# 验证文件结构
python generate_method2_outputs.py --verify
```
