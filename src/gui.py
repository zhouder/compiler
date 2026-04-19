import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from main import PROJECT_ROOT, compile_file_result


STAGES = (
    ("TOKENS", "词法"),
    ("AST", "语法树"),
    ("SEMANTIC", "语义"),
    ("IR", "IR"),
    ("ASM", "ASM"),
)

COLOR = {
    "app": "#eef1f5",
    "surface": "#fbfcfd",
    "surface_alt": "#f4f6f8",
    "border": "#ccd5df",
    "divider": "#e4e9ee",
    "text": "#171b20",
    "muted": "#66717e",
    "accent": "#107c72",
    "accent_hover": "#0b665f",
    "accent_soft": "#d9f0ed",
    "accent_text": "#064c45",
    "danger": "#b42318",
    "code_bg": "#ffffff",
    "gutter": "#f3f6f8",
    "selection": "#cce7e3",
}


def choose_font(candidates, fallback):
    families = set(tkfont.families())
    return next((name for name in candidates if name in families), fallback)


class FontSet:
    def __init__(self):
        ui = choose_font(("Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI"), "Microsoft YaHei UI")
        mono = choose_font(("Cascadia Mono", "JetBrains Mono", "Consolas"), "Consolas")
        self.hero = (ui, 17, "bold")
        self.title = (ui, 12, "bold")
        self.ui = (ui, 10)
        self.ui_bold = (ui, 10, "bold")
        self.small = (ui, 9)
        self.code = (mono, 10)
        self.code_small = (mono, 9)


class FlatButton(tk.Frame):
    def __init__(self, parent, text, command, fonts, primary=False):
        bg = COLOR["accent"] if primary else COLOR["surface_alt"]
        fg = "#ffffff" if primary else COLOR["text"]
        super().__init__(parent, bg=bg, cursor="hand2", padx=9, pady=4)
        self.command = command
        self.primary = primary
        self.label = tk.Label(self, text=text, bg=bg, fg=fg, font=fonts.ui_bold if primary else fonts.ui)
        self.label.pack()
        for widget in (self, self.label):
            widget.bind("<Button-1>", self.on_click)
            widget.bind("<Enter>", self.on_enter)
            widget.bind("<Leave>", self.on_leave)

    def on_click(self, event=None):
        self.command()

    def on_enter(self, event=None):
        bg = COLOR["accent_hover"] if self.primary else COLOR["divider"]
        fg = "#ffffff" if self.primary else COLOR["text"]
        self.apply_colors(bg, fg)

    def on_leave(self, event=None):
        bg = COLOR["accent"] if self.primary else COLOR["surface_alt"]
        fg = "#ffffff" if self.primary else COLOR["text"]
        self.apply_colors(bg, fg)

    def apply_colors(self, bg, fg):
        self.configure(bg=bg)
        self.label.configure(bg=bg, fg=fg)


class StageTab(tk.Frame):
    def __init__(self, parent, key, title, command, fonts):
        super().__init__(parent, bg=COLOR["surface"], cursor="hand2")
        self.key = key
        self.command = command
        self.selected = False
        self.title_label = tk.Label(self, text=title, bg=COLOR["surface"], fg=COLOR["text"], font=fonts.ui_bold)
        self.indicator = tk.Frame(self, height=2, bg=COLOR["surface"])

        self.title_label.pack(side=tk.LEFT, padx=(10, 10), pady=(5, 5))
        self.indicator.pack(side=tk.BOTTOM, fill=tk.X)

        for widget in (self, self.title_label, self.indicator):
            widget.bind("<Button-1>", self.on_click)
            widget.bind("<Enter>", self.on_enter)
            widget.bind("<Leave>", self.on_leave)

    def on_click(self, event=None):
        self.command(self.key)

    def on_enter(self, event=None):
        if not self.selected:
            self.apply_colors(COLOR["surface_alt"], COLOR["text"], COLOR["surface_alt"])

    def on_leave(self, event=None):
        self.set_selected(self.selected)

    def apply_colors(self, bg, title_fg, line_bg):
        self.configure(bg=bg)
        self.title_label.configure(bg=bg, fg=title_fg)
        self.indicator.configure(bg=line_bg)

    def set_selected(self, selected):
        self.selected = selected
        if selected:
            self.apply_colors(COLOR["accent_soft"], COLOR["accent_text"], COLOR["accent"])
        else:
            self.apply_colors(COLOR["surface"], COLOR["text"], COLOR["surface"])


class CodeBox(tk.Frame):
    def __init__(self, parent, fonts, readonly=False, compact=False):
        super().__init__(parent, bg=COLOR["border"], padx=1, pady=1)
        self.fonts = fonts
        self.readonly = readonly
        code_font = fonts.code_small if compact else fonts.code

        self.line_numbers = None
        if not readonly:
            self.line_numbers = tk.Canvas(self, width=52, bg=COLOR["gutter"], highlightthickness=0, bd=0)
            self.line_numbers.grid(row=0, column=0, sticky="ns")

        self.text = tk.Text(
            self,
            wrap=tk.NONE,
            undo=not readonly,
            bg=COLOR["code_bg"],
            fg=COLOR["text"],
            insertbackground=COLOR["accent"],
            selectbackground=COLOR["selection"],
            selectforeground=COLOR["text"],
            relief=tk.FLAT,
            padx=10,
            pady=8,
            font=code_font,
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
        if not self.line_numbers:
            return
        self.line_numbers.delete("all")
        index = self.text.index("@0,0")
        while True:
            dline = self.text.dlineinfo(index)
            if dline is None:
                break
            y = dline[1]
            line_no = index.split(".")[0]
            self.line_numbers.create_text(
                42,
                y,
                anchor="ne",
                text=line_no,
                fill=COLOR["muted"],
                font=self.fonts.code_small,
            )
            index = self.text.index(f"{index}+1line")


class CompilerGUI:
    def __init__(self, root):
        self.root = root
        self.fonts = FontSet()
        self.root.title("C语言编译器")
        self.root.geometry("1380x840")
        self.root.minsize(1120, 720)

        self.current_file = PROJECT_ROOT / "examples" / "test.c"
        self.stage_outputs = {key: "" for key, _ in STAGES}
        self.stage_tabs = {}
        self.current_stage = "TOKENS"
        self.file_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="就绪")
        self.summary_var = tk.StringVar(value="尚未编译")

        self.configure_style()
        self.build_menu()
        self.build_layout()
        self.load_file(self.current_file)
        self.select_stage("TOKENS")

    def configure_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.root.configure(bg=COLOR["app"])
        style.configure(".", font=self.fonts.ui)
        style.configure("App.TFrame", background=COLOR["app"])
        style.configure("Surface.TFrame", background=COLOR["surface"])
        style.configure("Panel.TFrame", background=COLOR["surface"], relief=tk.FLAT)
        style.configure("Toolbar.TFrame", background=COLOR["surface"])
        style.configure("Title.TLabel", background=COLOR["app"], foreground=COLOR["text"], font=self.fonts.hero)
        style.configure("Subtitle.TLabel", background=COLOR["app"], foreground=COLOR["muted"], font=self.fonts.ui)
        style.configure("Section.TLabel", background=COLOR["surface"], foreground=COLOR["text"], font=self.fonts.title)
        style.configure("Hint.TLabel", background=COLOR["surface"], foreground=COLOR["muted"], font=self.fonts.small)
        style.configure("Status.TLabel", background=COLOR["surface"], foreground=COLOR["muted"], font=self.fonts.small)
        style.configure("Badge.TLabel", background=COLOR["accent_soft"], foreground=COLOR["accent_text"], font=self.fonts.ui_bold, padding=(10, 4))

    def build_menu(self):
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="打开 C 文件", command=self.open_file)
        file_menu.add_command(label="保存", command=self.save_file)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.destroy)
        menu.add_cascade(label="文件", menu=file_menu)

        build_menu = tk.Menu(menu, tearoff=False)
        build_menu.add_command(label="开始编译", command=self.compile_current)
        build_menu.add_command(label="清空结果", command=self.clear_results)
        menu.add_cascade(label="编译", menu=build_menu)
        self.root.config(menu=menu)

    def build_layout(self):
        top = ttk.Frame(self.root, style="App.TFrame", padding=(22, 10, 22, 6))
        top.pack(fill=tk.X)

        title_group = ttk.Frame(top, style="App.TFrame")
        title_group.pack(side=tk.LEFT)
        ttk.Label(title_group, text="C语言编译器", style="Title.TLabel").pack(side=tk.LEFT)
        FlatButton(title_group, "打开", self.open_file, self.fonts).pack(side=tk.LEFT, padx=(18, 0))
        FlatButton(title_group, "保存", self.save_file, self.fonts).pack(side=tk.LEFT, padx=(7, 0))
        FlatButton(title_group, "编译", self.compile_current, self.fonts, primary=True).pack(side=tk.LEFT, padx=(7, 0))
        FlatButton(title_group, "清空", self.clear_results, self.fonts).pack(side=tk.LEFT, padx=(7, 0))
        ttk.Label(top, textvariable=self.summary_var, style="Badge.TLabel").pack(side=tk.RIGHT)

        content = ttk.Frame(self.root, style="App.TFrame", padding=(22, 6, 22, 8))
        content.pack(fill=tk.BOTH, expand=True)

        self.paned = ttk.PanedWindow(content, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        left = self.make_panel(self.paned, "源程序")
        right = self.make_panel(self.paned, "阶段输出")
        self.paned.add(left, weight=3)
        self.paned.add(right, weight=9)
        self.root.after(200, self.set_initial_pane_position)

        self.editor = CodeBox(left.body, self.fonts, readonly=False)
        self.editor.pack(fill=tk.BOTH, expand=True)

        tab_bar = tk.Frame(right.header_actions, bg=COLOR["surface"])
        tab_bar.pack(side=tk.RIGHT)
        for key, title in STAGES:
            tab = StageTab(tab_bar, key, title, self.select_stage, self.fonts)
            tab.pack(side=tk.LEFT, padx=(0, 3))
            self.stage_tabs[key] = tab

        FlatButton(tab_bar, "复制", self.copy_current_output, self.fonts).pack(side=tk.LEFT, padx=(3, 0))

        self.output_viewer = CodeBox(right.body, self.fonts, readonly=True, compact=True)
        self.output_viewer.pack(fill=tk.BOTH, expand=True)

        status = ttk.Frame(self.root, style="Toolbar.TFrame", padding=(12, 5))
        status.pack(side=tk.BOTTOM, fill=tk.X, padx=22, pady=(0, 8))
        ttk.Label(status, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.LEFT)
        ttk.Label(status, textvariable=self.file_var, style="Status.TLabel").pack(side=tk.LEFT, padx=(18, 0))
        ttk.Label(status, text="输出目录：output/", style="Status.TLabel").pack(side=tk.RIGHT)

    def make_panel(self, parent, title):
        outer = ttk.Frame(parent, style="App.TFrame", padding=(0, 0, 10, 0))
        panel = ttk.Frame(outer, style="Panel.TFrame", padding=10)
        panel.pack(fill=tk.BOTH, expand=True)

        title_row = ttk.Frame(panel, style="Surface.TFrame")
        title_row.pack(fill=tk.X)
        ttk.Label(title_row, text=title, style="Section.TLabel").pack(side=tk.LEFT)
        header_actions = tk.Frame(title_row, bg=COLOR["surface"])
        header_actions.pack(side=tk.RIGHT)

        body = ttk.Frame(panel, style="Surface.TFrame")
        body.pack(fill=tk.BOTH, expand=True, pady=(7, 0))
        outer.body = body
        outer.header_actions = header_actions
        return outer

    def set_initial_pane_position(self):
        width = self.paned.winfo_width()
        if width > 0:
            left_width = max(420, min(int(width * 0.36), width - 640))
            self.paned.sashpos(0, left_width)

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
        self.file_var.set(str(path))
        self.status_var.set("已打开源文件")

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
            if not path:
                return False
            self.current_file = Path(path)
        try:
            self.current_file.write_text(self.editor.get().rstrip() + "\n", encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc))
            return False
        self.file_var.set(str(self.current_file))
        self.status_var.set("已保存")
        return True

    def compile_current(self):
        if not self.save_file():
            return
        try:
            result = compile_file_result(str(self.current_file))
        except Exception as exc:
            messagebox.showerror("编译失败", str(exc))
            return

        section_map = {title: body for title, body in result.sections}
        for key, _ in STAGES:
            self.stage_outputs[key] = section_map.get(key, "")
        if "ERROR" in section_map:
            self.stage_outputs["SEMANTIC"] = section_map["ERROR"]
        self.select_stage(self.current_stage)

        if result.ok:
            self.status_var.set(f"编译通过，结果已写入 {result.output_dir}")
            self.summary_var.set("编译通过")
        else:
            self.status_var.set("编译失败，请查看语义分析或当前阶段输出")
            self.summary_var.set("编译失败")

    def clear_results(self):
        self.stage_outputs = {key: "" for key, _ in STAGES}
        self.select_stage(self.current_stage)
        self.summary_var.set("尚未编译")
        self.status_var.set("已清空结果")

    def copy_current_output(self):
        content = self.stage_outputs.get(self.current_stage, "")
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.status_var.set(f"已复制 {self.current_stage} 输出")


def main():
    root = tk.Tk()
    CompilerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
