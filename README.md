# compiler

一个面向 C 子集的编译原理课程设计项目。项目主流程为：

```text
源程序 -> 词法分析 -> 语法分析 -> 语义分析 -> 中间代码 IR -> 目标代码 ASM
```

主程序会在控制台输出 `TOKENS`、`AST`、`SEMANTIC`、`IR`、`ASM`，并把各阶段结果写入 `output/` 目录。

## 项目结构

```text
compiler/
├─ examples/
│  └─ test.c                 # 测试源程序
├─ src/
│  ├─ lexer/                 # 词法分析
│  ├─ parser/                # 递归下降语法分析与 AST
│  ├─ semantic/              # 语义分析与符号表
│  ├─ ir/                    # 四元式 IR 生成
│  ├─ codegen/               # 目标汇编代码生成
│  ├─ main.py                # 命令行入口
│  └─ gui.py                 # 可视化界面入口
├─ output/                   # 运行后生成，保存各阶段输出
├─ README.md
└─ TEAM.md
```

`output/` 是生成目录，可以随时清空；`__pycache__/` 也是 Python 缓存目录，不属于项目代码。

## 各阶段输入输出

| 阶段 | 输入 | 输出 | 主要目录 |
|---|---|---|---|
| 词法分析 | C 子集源程序文本 | Token 序列 | `src/lexer/` |
| 语法分析 | Token 序列 | AST 抽象语法树 | `src/parser/` |
| 语义分析 | AST | 语义检查结果、符号表检查 | `src/semantic/` |
| 中间代码生成 | AST | 四元式 IR | `src/ir/` |
| 目标代码生成 | 四元式 IR | ML615/MASM 风格 16 位 DOS 汇编 | `src/codegen/` |

## codegen 的作用

`src/codegen/code_generator.py` 是目标代码生成模块。

它接收 IR 生成器产生的四元式序列，把中间代码翻译成 ML615/MASM 风格的 16 位 DOS 汇编。它主要负责：

- 生成 `.MODEL SMALL`、`.STACK`、`.DATA`、`.CODE` 等汇编结构；
- 为变量、数组、临时变量、结构体字段分配数据区符号；
- 把四元式中的赋值、算术、比较、跳转、函数调用翻译成汇编指令；
- 处理数组访问、结构体字段访问、函数参数传递；
- 为 `printf`、`scanf` 生成简单的输入输出调用；
- 内置 `PRINT_INT`、`PRINT_STR`、`PRINT_CHAR`、`READ_INT` 等简单 DOS 中断运行时过程。

也就是说，`codegen` 是编译流程最后一步：

```text
IR 四元式 -> ASM 汇编代码
```

## 支持的语言子集

当前支持：

- `#include <stdio.h>` 的识别和保留；
- 基本类型：`int`、`char`、`float`、`void`；
- 结构体类型、简单指针类型；
- 全局结构体定义；
- 函数定义、函数参数、函数调用；
- 变量定义、数组定义、结构体变量定义；
- 赋值语句、数组元素赋值、结构体字段赋值；
- 表达式：算术、关系、逻辑、一元表达式；
- `if / else`、`while`、`for`、`do while`；
- `break`、`continue`、`return`；
- `printf(...)`、`scanf("%d", &a)`、`scanf("%d", &p.x)`；
- 作用域符号表、重复定义检查、未定义检查、基础类型检查；
- 函数参数数量和类型检查；
- 数组下标检查、结构体字段检查；
- 控制流四元式和标签回填。

暂不支持或支持不完整：

- 完整 C 预处理器；
- 数组初始化列表，例如 `int a[3] = {1, 2, 3};`；
- 完整指针运算和动态内存管理；
- `typedef`、`enum`、`union`；
- `switch case`；
- `i++`、`i--`；
- 完整浮点汇编运算，当前 ASM 后端主要按整数路径生成；
- 完整 C 标准库。

## 运行课程设计主流程

命令行方式：

在项目根目录执行：

```powershell
python src\main.py examples\test.c
```

运行后会生成：

```text
output/test.tokens.txt
output/test.ast.txt
output/test.ir.txt
output/test.asm
output/test.log.txt
```

其中：

- `test.tokens.txt`：词法分析结果；
- `test.ast.txt`：语法分析得到的 AST；
- `test.ir.txt`：中间代码四元式；
- `test.asm`：目标汇编代码；
- `test.log.txt`：整次编译过程的汇总输出。

可视化界面方式：

```powershell
python src\gui.py
```

界面支持：

- 打开和编辑 C 源程序；
- 保存当前源程序；
- 点击按钮执行完整编译流程；
- 通过阶段导航查看 `TOKENS`、`AST`、`SEMANTIC`、`IR`、`ASM`；
- 编译结果仍会写入 `output/` 目录。

## 手动验证 ASM

本项目不再提供 `tools` 脚本。ASM 验证可以在 VSCode 终端里手动完成。

先生成 ASM：

```powershell
python src\main.py examples\test.c
```

进入输出目录：

```powershell
cd output
```

使用 ML615 汇编：

```powershell
D:\Assembly\ML615\ml.exe /c test.asm
```

链接生成 EXE：

```powershell
D:\Assembly\ML615\link.exe test.obj;
```

生成的文件位于 `output/`：

```text
test.asm
test.obj
test.exe
```

如果系统大小写显示成 `TEST.OBJ`、`TEST.EXE` 也正常，Windows 文件名不区分大小写。

16 位 DOS 程序通常不能直接在 64 位 Windows 终端运行，需要用 DOSBox。可以手动打开 DOSBox 后挂载 `output` 目录，例如：

```bat
mount c D:\study\编译原理\编译原理课程设计\compiler\output
c:
test.exe
```

如果 DOSBox 不支持中文路径，建议把 `output` 里的 `test.exe` 临时复制到纯英文路径，例如 `D:\asmrun`，再挂载运行。
