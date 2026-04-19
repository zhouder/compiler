import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from main import PROJECT_ROOT, compile_file_result

STAGES = (
    ("TOKENS", "词法分析 (Tokens)"),
    ("AST", "抽象语法树 (AST)"),
    ("SEMANTIC", "语义分析 (Semantic)"),
    ("IR", "中间代码 (IR)"),
    ("ASM", "汇编代码 (ASM)"),
)

# 现代 IDE (VS Code) 风格的暗黑配色方案
COLOR = {
    "app_bg": "#1e1e1e",         # 整体应用背景
    "panel_bg": "#252526",       # 侧边栏/面板背景
    "border": "#3c3c3c",         # 分割线和边框
    "text": "#f0f0f0",           # 常规文本 (代码区域)，更清晰
    "text_ui": "#e0e0e0",        # UI 文本
    "muted": "#9e9e9e",          # 弱化文本 (行号, 提示)
    "accent": "#0e639c",         # 强调色 (按钮, 激活状态)
    "accent_hover": "#1177bb",   # 强调色悬浮
    "tab_active": "#1e1e1e",     # 激活的标签页背景
    "tab_inactive": "#2d2d2d",   # 未激活的标签页背景
    "selection": "#264f78",      # 文本选中背景
    "button_bg": "#3c3c3c",      # 普通按钮背景
    "button_hover": "#4d4d4d",   # 普通按钮悬浮
    "danger": "#f14c4c",         # 错误警告色
    "scrollbar_thumb": "#686868",# [修改] 更亮的滚动条滑块，确保清晰可见
    "scrollbar_hover": "#9e9e9e",# [修改] 滚动条悬浮时更亮
}

def choose_font(candidates, fallback):
    families = set(tkfont.families())
    return next((name for name in candidates if name in families), fallback)

class FontSet:
    def __init__(self):
        ui = choose_font(("Segoe UI Variable", "Microsoft YaHei UI", "Segoe UI"), "sans-serif")
        mono = choose_font(("Cascadia Code", "JetBrains Mono", "Consolas", "Courier New"), "monospace")
        self.hero = (ui, 14, "bold")
        self.title = (ui, 11, "bold")
        self.ui = (ui, 10)
        self.ui_bold = (ui, 10, "bold")
        self.small = (ui, 9)
        self.code = (mono, 12)       # 代码字体大小 12
        self.code_small = (mono, 10)

class ModernButton(tk.Frame):
    def __init__(self, parent, text, command, fonts, primary=False):
        self.primary = primary
        self.bg_color = COLOR["accent"] if primary else COLOR["button_bg"]
        self.hover_color = COLOR["accent_hover"] if primary else COLOR["button_hover"]
        self.fg_color = "#ffffff" if primary else COLOR["text_ui"]
        
        super().__init__(parent, bg=self.bg_color, cursor="hand2")
        self.command = command
        
        self.label = tk.Label(self, text=text, bg=self.bg_color, fg=self.fg_color, 
                              font=fonts.ui, padx=16, pady=6)
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
        
        self.title_label = tk.Label(self, text=title, bg=COLOR["tab_inactive"], 
                                    fg=COLOR["muted"], font=fonts.ui, padx=14, pady=8)
        
        # 顶部高亮指示条 (模仿 VS Code)
        self.indicator = tk.Frame(self, height=2, bg=COLOR["tab_inactive"])
        
        self.indicator.pack(side=tk.TOP, fill=tk.X)
        self.title_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        for widget in (self, self.title_label, self.indicator):
            widget.bind("<Button-1>", self.on_click)
            widget.bind("<Enter>", self.on_enter)
            widget.bind("<Leave>", self.on_leave)

    def on_click(self, event=None):
        self.command(self.key)

    def on_enter(self, event=None):
        if not self.selected:
            self.title_label.configure(fg=COLOR["text_ui"])

    def on_leave(self, event=None):
        if not self.selected:
            self.title_label.configure(fg=COLOR["muted"])

    def set_selected(self, selected):
        self.selected = selected
        bg = COLOR["tab_active"] if selected else COLOR["tab_inactive"]
        fg = COLOR["text_ui"] if selected else COLOR["muted"]
        indicator_color = COLOR["accent"] if selected else COLOR["tab_inactive"]
        
        self.configure(bg=bg)
        self.title_label.configure(bg=bg, fg=fg)
        self.indicator.configure(bg=indicator_color)

class ModernCodeBox(tk.Frame):
    def __init__(self, parent, fonts, readonly=False):
        super().__init__(parent, bg=COLOR["app_bg"])
        self.fonts = fonts
        self.readonly = readonly

        self.line_numbers = None
        if not readonly:
            self.line_numbers = tk.Canvas(self, width=45, bg=COLOR["app_bg"], highlightthickness=0, bd=0)
            self.line_numbers.grid(row=0, column=0, sticky="ns")

        self.text = tk.Text(
            self, wrap=tk.NONE, undo=not readonly,
            bg=COLOR["app_bg"], fg=COLOR["text"],
            insertbackground=COLOR["text"],          # 光标颜色
            selectbackground=COLOR["selection"],     # 选中颜色
            selectforeground=COLOR["text"],
            relief=tk.FLAT, bd=0, highlightthickness=0,
            padx=10, pady=10,
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

        if self.line_numbers:
            for event in ("<KeyRelease>", "<MouseWheel>", "<ButtonRelease-1>", "<Configure>"):
                self.text.bind(event, self.refresh_line_numbers)
        self.set("")

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
            self.line_numbers.create_text(
                35, y, anchor="ne", text=line_no, 
                fill=COLOR["muted"], font=self.fonts.code_small
            )
            index = self.text.index(f"{index}+1line")

class CompilerGUI:
    def __init__(self, root):
        self.root = root
        self.fonts = FontSet()
        self.root.title("C Compiler Studio")
        self.root.geometry("1400x850")
        self.root.minsize(1200, 700)
        self.root.configure(bg=COLOR["app_bg"])

        self.current_file = PROJECT_ROOT / "examples" / "test.c"
        self.stage_outputs = {key: "" for key, _ in STAGES}
        self.stage_tabs = {}
        self.current_stage = "TOKENS"

        self.configure_styles()
        self.build_menu()
        self.build_layout()
        self.load_file(self.current_file)
        self.select_stage("TOKENS")

    def configure_styles(self):
        style = ttk.Style()
        try: style.theme_use("clam")
        except tk.TclError: pass

        # [修改滚动条] 恢复箭头，并显著提高滑块对比度，彻底解决看不清的问题
        style.configure("TScrollbar", 
                        background=COLOR["scrollbar_thumb"], # 明显的灰色滑块
                        troughcolor=COLOR["app_bg"],         # 轨道颜色融入背景
                        bordercolor=COLOR["app_bg"], 
                        arrowcolor="#ffffff",                # 白色箭头更显眼
                        relief="flat")
        style.map("TScrollbar", background=[("active", COLOR["scrollbar_hover"])])
        
        style.configure("Sash", background=COLOR["border"], sashthickness=2)
        style.configure("TPanedwindow", background=COLOR["app_bg"])

    def build_menu(self):
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="打开源文件 (Open)", command=self.open_file)
        file_menu.add_command(label="保存 (Save)", command=self.save_file)
        file_menu.add_separator()
        file_menu.add_command(label="退出 (Exit)", command=self.root.destroy)
        menu.add_cascade(label="文件 (File)", menu=file_menu)

        build_menu = tk.Menu(menu, tearoff=False)
        build_menu.add_command(label="执行编译 (Build)", command=self.compile_current)
        build_menu.add_command(label="清空输出 (Clear)", command=self.clear_results)
        menu.add_cascade(label="运行 (Run)", menu=build_menu)
        self.root.config(menu=menu)

    def build_layout(self):
        # --- 顶部工具栏 (Toolbar) ---
        toolbar = tk.Frame(self.root, bg=COLOR["panel_bg"], height=60)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        toolbar.pack_propagate(False)

        title_lbl = tk.Label(toolbar, text="C Compiler", bg=COLOR["panel_bg"], 
                             fg=COLOR["text"], font=self.fonts.hero)
        title_lbl.pack(side=tk.LEFT, padx=20)

        # 工具栏按钮区域
        btn_frame = tk.Frame(toolbar, bg=COLOR["panel_bg"])
        btn_frame.pack(side=tk.LEFT, padx=20)
        
        ModernButton(btn_frame, "打开", self.open_file, self.fonts).pack(side=tk.LEFT, padx=5)
        ModernButton(btn_frame, "保存", self.save_file, self.fonts).pack(side=tk.LEFT, padx=5)
        ModernButton(btn_frame, "清空", self.clear_results, self.fonts).pack(side=tk.LEFT, padx=5)
        # 编译按钮高亮
        ModernButton(btn_frame, "▶ 开始编译", self.compile_current, self.fonts, primary=True).pack(side=tk.LEFT, padx=15)

        # --- 主内容区域 (分屏设计) ---
        # 注意：这里已经删除了原本的底部 Status Bar 代码
        content = tk.Frame(self.root, bg=COLOR["border"]) # 利用border颜色做1px分割线
        content.pack(fill=tk.BOTH, expand=True)

        self.paned = ttk.PanedWindow(content, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=0, pady=1)

        # 左侧代码编辑器
        left_panel = tk.Frame(self.paned, bg=COLOR["app_bg"])
        editor_header = tk.Frame(left_panel, bg=COLOR["tab_active"], height=35)
        editor_header.pack(side=tk.TOP, fill=tk.X)
        editor_header.pack_propagate(False)
        tk.Label(editor_header, text="SOURCE CODE", bg=COLOR["tab_active"], fg=COLOR["muted"], 
                 font=self.fonts.small).pack(side=tk.LEFT, padx=15)
        
        self.editor = ModernCodeBox(left_panel, self.fonts, readonly=False)
        self.editor.pack(fill=tk.BOTH, expand=True)

        # 右侧输出浏览器
        right_panel = tk.Frame(self.paned, bg=COLOR["app_bg"])
        
        # 右侧顶部 Tabs 栏
        tabs_header = tk.Frame(right_panel, bg=COLOR["panel_bg"], height=35)
        tabs_header.pack(side=tk.TOP, fill=tk.X)
        
        tab_container = tk.Frame(tabs_header, bg=COLOR["panel_bg"])
        tab_container.pack(side=tk.LEFT)
        for key, title in STAGES:
            tab = EditorTab(tab_container, key, title, self.select_stage, self.fonts)
            tab.pack(side=tk.LEFT, padx=(0, 1)) # 1px 间距
            self.stage_tabs[key] = tab
            
        # 复制按钮放到右侧
        ModernButton(tabs_header, "复制输出", self.copy_current_output, self.fonts).pack(side=tk.RIGHT, padx=10, pady=2)

        self.output_viewer = ModernCodeBox(right_panel, self.fonts, readonly=True)
        self.output_viewer.pack(fill=tk.BOTH, expand=True)

        self.paned.add(left_panel, weight=3)
        self.paned.add(right_panel, weight=7)
        
        # 强制设置初始比例为 3:7 (输入区窄，输出区宽)
        self.root.after(200, self.set_initial_pane_position)

    def set_initial_pane_position(self):
        """强制分配 PanedWindow 的比例"""
        width = self.paned.winfo_width()
        if width > 100:
            # 强制将分割线设置在总宽度的 30% 处
            self.paned.sashpos(0, int(width * 0.3))

    def update_window_title(self):
        """将文件路径显示在标题栏上，代替原先的底部状态栏"""
        if self.current_file:
            self.root.title(f"C Compiler Studio - {self.current_file}")
        else:
            self.root.title("C Compiler Studio")

    def select_stage(self, key):
        self.current_stage = key
        for stage_key, tab in self.stage_tabs.items():
            tab.set_selected(stage_key == key)
        self.output_viewer.set(self.stage_outputs.get(key, ""))

    def load_file(self, path):
        path = Path(path)
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("打开失败", str(exc))
            return
        self.current_file = path
        self.editor.set(content)
        self.update_window_title()

    def open_file(self):
        path = filedialog.askopenfilename(
            initialdir=PROJECT_ROOT / "examples",
            filetypes=[("C source", "*.c"), ("All files", "*.*")],
        )
        if path:
            self.load_file(path)

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
        self.update_window_title()
        return True

    def compile_current(self):
        if not self.save_file(): return
        
        self.root.update()
        try:
            result = compile_file_result(str(self.current_file))
        except Exception as exc:
            messagebox.showerror("编译异常", f"执行遇到错误:\n{str(exc)}")
            return

        section_map = {title: body for title, body in result.sections}
        for key, _ in STAGES:
            self.stage_outputs[key] = section_map.get(key, "")
        if "ERROR" in section_map:
            self.stage_outputs["SEMANTIC"] = section_map["ERROR"]
        
        self.select_stage(self.current_stage)

        if not result.ok:
            # 如果编译失败，直接弹窗警告，并跳转到错误页面
            messagebox.showwarning("编译失败", "发现语法或语义错误，请检查对应输出面板。")
            if "ERROR" in section_map:
                self.select_stage("SEMANTIC")

    def clear_results(self):
        self.stage_outputs = {key: "" for key, _ in STAGES}
        self.select_stage(self.current_stage)

    def copy_current_output(self):
        content = self.stage_outputs.get(self.current_stage, "")
        if not content.strip():
            messagebox.showinfo("提示", "当前内容为空，无法复制。")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("复制成功", f"[{self.current_stage}] 阶段的内容已复制到剪贴板！")

def main():
    root = tk.Tk()
    CompilerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()