"""桌面可视化界面。

界面基于 tkinter，主要用于课堂展示：左侧编辑 C 子集源码，右侧查看
词法、AST、语义、IR 和 ASM 各阶段结果。
"""

import sys
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from main import PROJECT_ROOT, compile_file_result

STAGES = (
    ("TOKENS", "词法 Tokens"),
    ("AST", "语法 AST"),
    ("SEMANTIC", "语义 Semantic"),
    ("IR", "中间代码 IR"),
    ("ASM", "汇编 ASM"),
)

EMPTY_OUTPUT = {
    "TOKENS": "尚未生成词法分析结果。",
    "AST": "尚未生成抽象语法树。",
    "SEMANTIC": "尚未生成语义分析结果。",
    "IR": "尚未生成中间代码。",
    "ASM": "尚未生成汇编代码。",
}

# 轻量 IDE 风格配色，减少大面积高饱和渐变和系统默认控件感。
COLOR = {
    "app_bg": "#0f131a",
    "panel_bg": "#151a22",
    "panel_alt": "#1a202b",
    "code_bg": "#0b1018",
    "border": "#273142",
    "border_soft": "#202838",
    "text": "#e5edf5",
    "text_ui": "#d7dee8",
    "muted": "#8d98a8",
    "accent": "#2fbf9f",
    "accent_hover": "#35d0ad",
    "accent_blue": "#5aa2ff",
    "selection": "#203a52",
    "button_bg": "#1d2531",
    "button_hover": "#263241",
    "tab_active": "#202838",
    "tab_inactive": "#151a22",
    
    # 语法高亮颜色
    "syn_keyword": "#569cd6",    # 蓝色 (if, while)
    "syn_type": "#4ec9b0",       # 青色 (int, struct)
    "syn_string": "#ce9178",     # 橙色 ("hello")
    "syn_comment": "#6a9955",    # 绿色 (// comment)
    "syn_number": "#b5cea8",     # 浅绿 (123)
    "syn_function": "#dcdcaa",   # 黄色 (printf)
    "syn_error": "#ff6b6b",      # 红色 (Error)
}

# 简单的 C 语言高亮正则规则
SYNTAX_RULES = {
    "Comment": r'(//[^\n]*|/\*[\s\S]*?\*/)',
    "String": r'(".*?"|\'.*?\')',
    "Type": r'\b(int|void|char|float|double|struct|long|short|unsigned|signed)\b',
    "Keyword": r'\b(if|else|while|for|do|return|break|continue|switch|case|default)\b',
    "Number": r'\b\d+(\.\d+)?\b',
    "Function": r'\b([a-zA-Z_]\w*)\s*(?=\()',
}

def choose_font(candidates, fallback):
    """从候选字体中选择当前系统可用的字体。"""

    families = set(tkfont.families())
    return next((name for name in candidates if name in families), fallback)

class FontSet:
    """集中管理界面字体，方便统一调整字号。"""

    def __init__(self):
        ui = choose_font(("Segoe UI", "Microsoft YaHei UI", "Arial"), "sans-serif")
        mono = choose_font(("Consolas", "Cascadia Code", "JetBrains Mono", "Courier New"), "monospace")
        self.hero = (ui, 13, "bold")
        self.ui = (ui, 10)
        self.small = (ui, 9)
        self.label = (ui, 9, "bold")
        self.code = (mono, 11)
        self.code_small = (mono, 10)

class ModernButton(tk.Frame):
    """自绘按钮，用于统一主按钮和次按钮样式。"""

    def __init__(self, parent, text, command, fonts, primary=False):
        self.primary = primary
        self.bg_color = COLOR["accent"] if primary else COLOR["button_bg"]
        self.hover_color = COLOR["accent_hover"] if primary else COLOR["button_hover"]
        self.border_color = COLOR["accent"] if primary else COLOR["border"]
        self.fg_color = "#07120f" if primary else COLOR["text_ui"]
        
        super().__init__(
            parent,
            bg=self.bg_color,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=self.border_color,
            highlightcolor=self.border_color,
        )
        self.command = command
        
        self.label = tk.Label(
            self,
            text=text,
            bg=self.bg_color,
            fg=self.fg_color,
            font=fonts.ui,
            padx=15,
            pady=7,
        )
        self.label.pack(fill=tk.BOTH, expand=True)
        
        for widget in (self, self.label):
            widget.bind("<Button-1>", self.on_click)
            widget.bind("<Enter>", self.on_enter)
            widget.bind("<Leave>", self.on_leave)

    def on_click(self, event=None):
        self.command()

    def on_enter(self, event=None):
        self.configure(bg=self.hover_color)
        self.label.configure(bg=self.hover_color)

    def on_leave(self, event=None):
        self.configure(bg=self.bg_color)
        self.label.configure(bg=self.bg_color)

class EditorTab(tk.Frame):
    def __init__(self, parent, key, title, command, fonts):
        super().__init__(parent, bg=COLOR["tab_inactive"], cursor="hand2")
        self.key = key
        self.command = command
        self.selected = False
        
        self.title_label = tk.Label(
            self,
            text=title,
            bg=COLOR["tab_inactive"],
            fg=COLOR["muted"],
            font=fonts.ui,
            padx=14,
            pady=8,
        )
        self.indicator = tk.Frame(self, height=3, bg=COLOR["tab_inactive"])
        
        self.title_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.indicator.pack(side=tk.BOTTOM, fill=tk.X)

        for widget in (self, self.title_label, self.indicator):
            widget.bind("<Button-1>", self.on_click)
            widget.bind("<Enter>", self.on_enter)
            widget.bind("<Leave>", self.on_leave)

    def on_click(self, event=None):
        self.command(self.key)

    def on_enter(self, event=None):
        if not self.selected: self.title_label.configure(fg=COLOR["text_ui"])

    def on_leave(self, event=None):
        if not self.selected: self.title_label.configure(fg=COLOR["muted"])

    def set_selected(self, selected):
        self.selected = selected
        bg = COLOR["tab_active"] if selected else COLOR["tab_inactive"]
        fg = COLOR["text"] if selected else COLOR["muted"]
        ind_color = COLOR["accent"] if selected else COLOR["tab_inactive"]
        
        self.configure(bg=bg)
        self.title_label.configure(bg=bg, fg=fg)
        self.indicator.configure(bg=ind_color)

class ModernCodeBox(tk.Frame):
    def __init__(self, parent, fonts, readonly=False, enable_highlight=False):
        super().__init__(
            parent,
            bg=COLOR["border_soft"],
            highlightthickness=1,
            highlightbackground=COLOR["border"],
        )
        self.fonts = fonts
        self.readonly = readonly
        self.enable_highlight = enable_highlight

        self.line_numbers = None
        if not readonly:
            self.line_numbers = tk.Canvas(self, width=50, bg=COLOR["code_bg"], highlightthickness=0, bd=0)
            self.line_numbers.grid(row=0, column=0, sticky="ns")

        self.text = tk.Text(
            self, wrap=tk.NONE, undo=not readonly,
            bg=COLOR["code_bg"], fg=COLOR["text"],
            insertbackground=COLOR["text"],          
            selectbackground=COLOR["selection"],     
            selectforeground=COLOR["text"],
            relief=tk.FLAT, bd=0, highlightthickness=0,
            padx=14, pady=12,
            font=fonts.code
        )
        
        self.yscroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.on_scrollbar)
        self.xscroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.text.xview)
        self.text.configure(yscrollcommand=self.on_text_scroll, xscrollcommand=self.xscroll.set)

        column = 1 if self.line_numbers else 0
        self.text.grid(row=0, column=column, sticky="nsew")
        self.yscroll.grid(row=0, column=column + 1, sticky="ns")
        self.xscroll.grid(row=1, column=column, sticky="ew")
        self.columnconfigure(column, weight=1)
        self.rowconfigure(0, weight=1)

        # 配置语法高亮 Tag
        if self.enable_highlight:
            self.text.tag_configure("Keyword", foreground=COLOR["syn_keyword"])
            self.text.tag_configure("Type", foreground=COLOR["syn_type"])
            self.text.tag_configure("String", foreground=COLOR["syn_string"])
            self.text.tag_configure("Comment", foreground=COLOR["syn_comment"])
            self.text.tag_configure("Number", foreground=COLOR["syn_number"])
            self.text.tag_configure("Function", foreground=COLOR["syn_function"])
            self.text.bind("<KeyRelease>", self.on_key_release)

        if self.line_numbers:
            for event in ("<MouseWheel>", "<ButtonRelease-1>", "<Configure>"):
                self.text.bind(event, self.refresh_line_numbers, add="+")
            self.text.bind("<KeyRelease>", self.refresh_line_numbers, add="+")
            
        self.set("")

    def on_key_release(self, event=None):
        # 避免方向键触发高亮导致性能问题，只在输入时触发
        if event and event.keysym in ("Up", "Down", "Left", "Right"): 
            return
        self.apply_highlight()

    def apply_highlight(self):
        if not self.enable_highlight: return
        content = self.text.get("1.0", tk.END)
        
        # 移除旧的高亮
        for tag in SYNTAX_RULES.keys():
            self.text.tag_remove(tag, "1.0", tk.END)

        # 重新计算高亮
        for tag, pattern in SYNTAX_RULES.items():
            for match in re.finditer(pattern, content):
                start_idx = f"1.0 + {match.start()} chars"
                end_idx = f"1.0 + {match.end()} chars"
                # 函数名的特殊处理（只高亮函数名部分）
                if tag == "Function":
                    start_idx = f"1.0 + {match.start(1)} chars"
                    end_idx = f"1.0 + {match.end(1)} chars"
                self.text.tag_add(tag, start_idx, end_idx)

    def on_scrollbar(self, *args):
        self.text.yview(*args)
        self.refresh_line_numbers()

    def on_text_scroll(self, first, last):
        self.yscroll.set(first, last)
        self.refresh_line_numbers()

    def get(self):
        return self.text.get("1.0", tk.END)

    def set(self, content):
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", content)
        if self.enable_highlight:
            self.apply_highlight()
        if self.readonly:
            self.text.configure(state=tk.DISABLED)
        self.refresh_line_numbers()

    def refresh_line_numbers(self, event=None):
        if not self.line_numbers: return
        self.line_numbers.delete("all")
        index = self.text.index("@0,0")
        while True:
            dline = self.text.dlineinfo(index)
            if dline is None: break
            y = dline[1]
            line_no = index.split(".")[0]
            # 行号颜色微调，更符合 IDE
            self.line_numbers.create_text(
                38, y, anchor="ne", text=line_no,
                fill=COLOR["muted"], font=self.fonts.code_small
            )
            index = self.text.index(f"{index}+1line")

class CompilerGUI:
    def __init__(self, root):
        self.root = root
        self.fonts = FontSet()
        self.root.title("C Compiler Studio")
        self.root.geometry("1480x860")
        self.root.minsize(1120, 680)
        self.root.configure(bg=COLOR["app_bg"])

        self.current_file = PROJECT_ROOT / "examples" / "test.c"
        self.stage_outputs = EMPTY_OUTPUT.copy()
        self.stage_tabs = {}
        self.current_stage = "TOKENS"
        
        self.status_var = tk.StringVar(value="就绪")

        self.configure_styles()
        self.build_menu()
        self.build_layout()
        self.load_file(self.current_file)
        self.select_stage("TOKENS")

    def configure_styles(self):
        style = ttk.Style()
        try: style.theme_use("clam")
        except tk.TclError: pass

        style.configure("TScrollbar", 
                        background="#4b5565",
                        troughcolor=COLOR["code_bg"],
                        bordercolor=COLOR["app_bg"],
                        arrowcolor=COLOR["muted"],
                        relief="flat")
        style.map("TScrollbar", background=[("active", "#667085")])
        
        style.configure("Sash", background=COLOR["border"], sashthickness=2)
        style.configure("TPanedwindow", background=COLOR["app_bg"])

    def build_menu(self):
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="打开 (Open)", command=self.open_file)
        file_menu.add_command(label="保存 (Save)", command=self.save_file)
        file_menu.add_separator()
        file_menu.add_command(label="退出 (Exit)", command=self.root.destroy)
        menu.add_cascade(label="文件", menu=file_menu)
        self.root.config(menu=menu)

    def build_layout(self):
        # --- 顶部工具栏 ---
        toolbar = tk.Frame(self.root, bg=COLOR["panel_bg"], height=62)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        toolbar.pack_propagate(False)

        title_frame = tk.Frame(toolbar, bg=COLOR["panel_bg"])
        title_frame.pack(side=tk.LEFT, padx=(18, 22), fill=tk.Y)
        tk.Label(
            title_frame,
            text="C Compiler Studio",
            bg=COLOR["panel_bg"],
            fg=COLOR["text"],
            font=self.fonts.hero,
        ).pack(side=tk.LEFT)

        btn_frame = tk.Frame(toolbar, bg=COLOR["panel_bg"])
        btn_frame.pack(side=tk.LEFT)
        
        ModernButton(btn_frame, "打开", self.open_file, self.fonts).pack(side=tk.LEFT, padx=(0, 8))
        ModernButton(btn_frame, "保存", self.save_file, self.fonts).pack(side=tk.LEFT, padx=(0, 8))
        ModernButton(btn_frame, "清空", self.clear_results, self.fonts).pack(side=tk.LEFT, padx=(0, 8))
        ModernButton(btn_frame, "开始编译", self.compile_current, self.fonts, primary=True).pack(side=tk.LEFT, padx=(10, 0))

        # --- 主内容区域 (分屏设计) ---
        content = tk.Frame(self.root, bg=COLOR["app_bg"])
        content.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        self.paned = ttk.PanedWindow(content, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        # 左侧代码编辑器 (开启语法高亮)
        left_panel = tk.Frame(
            self.paned,
            bg=COLOR["panel_bg"],
            highlightthickness=1,
            highlightbackground=COLOR["border"],
        )
        editor_header = tk.Frame(left_panel, bg=COLOR["panel_bg"], height=46)
        editor_header.pack(side=tk.TOP, fill=tk.X)
        editor_header.pack_propagate(False)
        
        tk.Label(
            editor_header,
            text="源代码",
            bg=COLOR["panel_bg"],
            fg=COLOR["text"],
            font=self.fonts.label,
        ).pack(side=tk.LEFT, padx=(14, 8))
        self.file_lbl = tk.Label(editor_header, text="未命名文件.c", bg=COLOR["panel_bg"],
                                 fg=COLOR["muted"], font=self.fonts.small)
        self.file_lbl.pack(side=tk.LEFT)
        
        self.editor = ModernCodeBox(left_panel, self.fonts, readonly=False, enable_highlight=True)
        self.editor.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # 右侧输出浏览器
        right_panel = tk.Frame(
            self.paned,
            bg=COLOR["panel_bg"],
            highlightthickness=1,
            highlightbackground=COLOR["border"],
        )
        
        tabs_header = tk.Frame(right_panel, bg=COLOR["panel_bg"], height=46)
        tabs_header.pack(side=tk.TOP, fill=tk.X)
        tabs_header.pack_propagate(False)
        
        tab_container = tk.Frame(tabs_header, bg=COLOR["panel_bg"])
        tab_container.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))
        for key, title in STAGES:
            tab = EditorTab(tab_container, key, title, self.select_stage, self.fonts)
            tab.pack(side=tk.LEFT, padx=(0, 2), fill=tk.Y)
            self.stage_tabs[key] = tab
            
        ModernButton(tabs_header, "复制", self.copy_current_output, self.fonts).pack(side=tk.RIGHT, padx=10, pady=7)

        self.output_viewer = ModernCodeBox(right_panel, self.fonts, readonly=True, enable_highlight=False)
        self.output_viewer.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.paned.add(left_panel, weight=1)
        self.paned.add(right_panel, weight=1)
        
        self.statusbar = tk.Frame(self.root, bg=COLOR["panel_alt"], height=28)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.statusbar.pack_propagate(False)

        tk.Label(self.statusbar, textvariable=self.status_var, bg=COLOR["panel_alt"], fg=COLOR["text_ui"],
                 font=self.fonts.small).pack(side=tk.LEFT, padx=10)
        tk.Label(self.statusbar, text="UTF-8  |  C subset  |  MASM 16-bit", bg=COLOR["panel_alt"], fg=COLOR["muted"],
                 font=self.fonts.small).pack(side=tk.RIGHT, padx=10)
        
        self.root.after(200, self.set_initial_pane_position)

    def set_initial_pane_position(self):
        width = self.paned.winfo_width()
        if width > 100:
            self.paned.sashpos(0, int(width * 0.47))

    def update_status(self, msg, is_error=False):
        self.status_var.set(msg)
        color = "#3a1f28" if is_error else COLOR["panel_alt"]
        
        if hasattr(self, 'statusbar'):
            self.statusbar.configure(bg=color) 
            for child in self.statusbar.winfo_children():
                try:
                    child.configure(bg=color)
                except tk.TclError:
                    pass

    def select_stage(self, key):
        self.current_stage = key
        for stage_key, tab in self.stage_tabs.items():
            tab.set_selected(stage_key == key)
            
        content = self.stage_outputs.get(key, "")
        self.output_viewer.set(content)
        
        # 如果是 ERROR，高亮显示
        if "ERROR" in key or "Exception" in content:
            self.output_viewer.text.tag_configure("ErrText", foreground=COLOR["syn_error"])
            self.output_viewer.text.tag_add("ErrText", "1.0", tk.END)

    def load_file(self, path):
        path = Path(path)
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("打开失败", str(exc))
            return
        self.current_file = path
        self.editor.set(content)
        self.file_lbl.configure(text=path.name)
        self.root.title(f"C Compiler Studio - {path}")
        self.update_status("就绪")

    def open_file(self):
        path = filedialog.askopenfilename(
            initialdir=PROJECT_ROOT / "examples",
            filetypes=[("C source", "*.c"), ("All files", "*.*")],
        )
        if path: self.load_file(path)

    def save_file(self):
        if not self.current_file:
            path = filedialog.asksaveasfilename(
                initialdir=PROJECT_ROOT / "examples",
                defaultextension=".c",
                filetypes=[("C source", "*.c"), ("All files", "*.*")],
            )
            if not path: return False
            self.current_file = Path(path)
        try:
            self.current_file.write_text(self.editor.get().rstrip() + "\n", encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc))
            return False
        self.file_lbl.configure(text=self.current_file.name)
        self.update_status("已保存")
        return True

    def compile_current(self):
        if not self.save_file(): return
        
        self.update_status("编译中...")
        self.root.update()
        try:
            result = compile_file_result(str(self.current_file))
        except Exception as exc:
            self.update_status("编译遇到异常", is_error=True)
            messagebox.showerror("编译异常", f"执行遇到错误:\n{str(exc)}")
            return

        section_map = {title: body for title, body in result.sections}
        for key, _ in STAGES:
            self.stage_outputs[key] = section_map.get(key, "")
        if "ERROR" in section_map:
            self.stage_outputs["SEMANTIC"] = section_map["ERROR"]
        
        self.select_stage(self.current_stage)

        if not result.ok:
            self.update_status("编译失败：请检查语法或语义错误", is_error=True)
            if "ERROR" in section_map:
                self.select_stage("SEMANTIC")
        else:
            self.update_status(f"编译成功：输出已写入 {result.output_dir.name}/ 目录", is_error=False)

    def clear_results(self):
        self.stage_outputs = EMPTY_OUTPUT.copy()
        self.select_stage(self.current_stage)
        self.update_status("输出已清空")

    def copy_current_output(self):
        content = self.stage_outputs.get(self.current_stage, "")
        if not content.strip(): return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.update_status(f"已复制 [{self.current_stage}] 内容到剪贴板")

def main():
    root = tk.Tk()
    CompilerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
