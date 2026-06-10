# Compiler

一个面向 C 子集的编译原理课程设计项目。项目主流程为：

```text
源程序 -> 词法分析 -> 语法分析 -> 语义分析 -> 中间代码 IR -> 目标代码 ASM
```

主程序会在控制台输出 `TOKENS`、`AST`、`SEMANTIC`、`IR`、`ASM`，并把各阶段结果写入 `output/` 目录。项目同时提供命令行、桌面 GUI 和网页版可视化界面。

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
│  ├─ gui.py                 # 桌面可视化界面入口
│  ├─ webapp.py              # 网页版可视化服务入口
│  └─ web/                   # 网页前端资源
├─ output/                   # 运行后生成，保存各阶段输出
└─ README.md
```


## 各阶段输入输出

| 阶段 | 输入 | 输出 | 主要目录 |
|---|---|---|---|
| 词法分析 | C 子集源程序文本 | Token 序列 | `src/lexer/` |
| 语法分析 | Token 序列 | AST 抽象语法树 | `src/parser/` |
| 语义分析 | AST | 语义检查结果、符号表检查 | `src/semantic/` |
| 中间代码生成 | AST | 四元式 IR | `src/ir/` |
| 目标代码生成 | 四元式 IR | ML615/MASM 风格 16 位 DOS 汇编 | `src/codegen/` |



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

网页版可视化界面方式：

```powershell
python -B src\webapp.py
```

启动后浏览器访问：

```text
http://127.0.0.1:8000
```

也可以指定端口，例如：

```powershell
python -B src\webapp.py 8080
```


## 手动验证 ASM

先生成 ASM：

```powershell
python src\main.py examples\test.c
```

16 位 DOS 程序通常不能直接在 64 位 Windows 终端运行，需要用 DOSBox。可以手动打开 DOSBox 后挂载 `output` 目录，例如：

```bat
mount w D:\Assembly
mount c D:\compiler\output
set PATH=w:\;%PATH%
c:
masm test.asm
link test.obj;
test
```

