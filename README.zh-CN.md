# 编译器

> 用 Python 实现的 C 子集编译器

<a href="./README.md">English</a> | <a href="./README.zh-CN.md">中文</a>

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

![编译器预览截图 — Web 界面深色模式下的 ASM 输出](docs/preview-zh.png)

## 编译流程

```
源程序 → 词法分析 → 语法分析 → 语义分析 → 中间代码 → 目标代码
```

功能特性：
- 词法分析器（Lexer）
- 递归下降语法分析器 + AST
- 语义分析与符号表
- 四元式 IR 生成
- 16 位 x86 汇编代码生成
- 命令行 + 桌面 GUI + 网页界面
- Web 端自适应浅色/深色主题，内置中英文切换

## 快速开始

```bash
git clone https://github.com/zhouder/compiler.git
cd compiler
python src/main.py examples/test.c
```

> **注意：** `output/` 目录在首次 clone 时为空，运行上述命令后会由编译器自动生成所有输出文件。

输出文件：
- `output/test.tokens.txt` — 词法分析结果
- `output/test.ast.txt` — 抽象语法树
- `output/test.ir.txt` — 中间代码四元式
- `output/test.asm` — 汇编代码

## 可视化界面

```bash
# 桌面 GUI
python src/gui.py

# 网页版（访问 http://127.0.0.1:8000）
python -B src/webapp.py
```

## 项目结构

```
compiler/
├── examples/
│   └── test.c              # 测试源程序
├── src/
│   ├── lexer/              # 词法分析
│   ├── parser/            # 语法分析 + AST
│   ├── semantic/          # 语义分析
│   ├── ir/                # 中间代码生成
│   ├── codegen/           # 代码生成
│   ├── main.py            # 命令行入口
│   ├── gui.py             # 桌面界面入口
│   └── webapp.py          # 网页入口
└── output/                # 生成的文件
```

## 支持的功能

| 功能 | 说明 |
|------|------|
| 基本类型 | `int`、`char`、`float`、`void` |
| 结构体、指针 | 用户自定义类型 |
| 函数 | 定义、参数、调用 |
| 数组、结构体变量 | 复杂数据类型 |
| 表达式 | 算术、关系、逻辑运算 |
| 控制流 | `if/else`、`while`、`for`、`do while` |
| 输入输出 | `printf`、`scanf` |
| 类型检查 | 作用域、符号表、类型检查 |

## 汇编验证

需要使用 DOSBox 运行 16 位程序（请将下方命令中的 `D:\compiler\output` 替换为你本地的 `output/` 绝对路径）：

```bat
mount c D:\compiler\output
c:
masm test.asm;
link test.obj;
test
```

## 许可证

MIT License — 见 [LICENSE](LICENSE)
