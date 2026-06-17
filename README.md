# Compiler / 编译器

> A compiler for C-subset language implemented in Python | 面向 C 子集的编译器课程设计

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Pipeline / 编译流程

```
Source Code → Lexer → Parser → Semantic → IR → ASM
源程序 → 词法分析 → 语法分析 → 语义分析 → 中间代码 → 目标代码
```

Features / 特性:
- Lexer (Tokenization) / 词法分析器
- Recursive Descent Parser + AST / 递归下降语法分析器
- Semantic Analysis + Symbol Table / 语义分析与符号表
- Quadruple IR Generation / 四元式 IR 生成
- 16-bit x86 ASM CodeGen / x86 汇编代码生成
- CLI + GUI + Web Interface / 命令行、桌面、Web 三种界面

## Quick Start / 快速开始

```powershell
# Install dependencies / 安装依赖
pip install -r requirements.txt 2>/dev/null || echo "No requirements.txt"

# Run / 运行
python src/main.py examples/test.c

# Output / 输出
# output/test.tokens.txt  - Tokens
# output/test.ast.txt     - AST
# output/test.ir.txt      - IR (Quadruples)
# output/test.asm         - ASM (x86)
```

## Visual Interface / 可视化界面

```powershell
# GUI / 桌面界面
python src/gui.py

# Web / 网页版
python -B src/webapp.py
# Visit / 访问 http://127.0.0.1:8000
```

## Project Structure / 项目结构

```
compiler/
├── examples/
│   └── test.c              # Test source / 测试源程序
├── src/
│   ├── lexer/             # Lexer / 词法分析
│   ├── parser/            # Parser + AST / 语法分析
│   ├── semantic/          # Semantic / 语义分析
│   ├── ir/                # IR Gen / 中间代码
│   ├── codegen/           # CodeGen / 代码生成
│   ├── main.py            # CLI entry / 命令行入口
│   ├── gui.py             # GUI entry / 桌面界面
│   └── webapp.py          # Web entry / 网页入口
└── output/                # Generated files / 生成文件
```

## Supported Features / 支持的功能

| Feature | 特性 |
|---------|------|
| Types: `int`, `char`, `float`, `void` | 基本类型 |
| Struct, Pointer | 结构体、指针 |
| Functions & Args | 函数与参数 |
| Arrays, Struct Variables | 数组、结构体变量 |
| Expressions | 表达式 |
| Control Flow | 控制流 (if/else/while/for) |
| I/O: `printf`, `scanf` | 输入输出 |
| Scope & Type Checking | 作用域、类型检查 |

## ASM Verification / 汇编验证

Requires DOSBox for 16-bit execution:

```bat
# In DOSBox / 在 DOSBox 中
mount c D:\compiler\output
c:
masm test.asm;
link test.obj;
test
```

## License / 许可证

MIT License - see [LICENSE](LICENSE)
