# compiler

编译原理课程设计项目骨架。

## 目标
实现一个基本 C 子集编译器，完成：

- 词法分析
- 语法分析
- 语义分析
- 中间代码生成
- 目标代码生成

## 建议支持的语言范围
先只做这些：

- `int`、`char`、`float`
- 变量定义和赋值
- `if-else`
- `while`
- `for`
- `printf`、`scanf`
- 算术表达式和关系表达式

先不要做这些：

- `struct`、`union`
- 指针
- 多文件
- 完整预处理
- 复杂函数系统

## 目录
```text
compiler/
├── README.md
├── TEAM.md
├── requirements.txt
├── .gitignore
├── src/
│   ├── lexer/
│   ├── parser/
│   ├── semantic/
│   ├── ir/
│   ├── codegen/
│   └── main.py
├── examples/
└── output/
```

## 运行
```bash
python src/main.py examples/test1.c
```

## 三人分工建议
见 `TEAM.md`。
