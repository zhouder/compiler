const LABELS = {
  en: {
    statusReady: "Ready",
    statusLoading: "Loading",
    statusCompiling: "Compiling",
    statusSuccess: "Success",
    statusError: "Error",
    compileBtn: "Compile",
    loadExampleBtn: "Load Example",
    langToggle: "中文",
    filenamePlaceholder: "Filename",
    sourceEditorLabel: "Source Code",
    stageResultsLabel: "Stage Results",
    fullscreen: "Fullscreen",
    exitFullscreen: "Exit",
    copy: "Copy",
    copied: "Copied",
    requestFailed: "Request failed",
    notGeneratedTokens: "Tokens not generated yet.",
    notGeneratedAST: "AST not generated yet.",
    notGeneratedSemantic: "Semantic analysis not generated yet.",
    notGeneratedIR: "IR not generated yet.",
    notGeneratedASM: "ASM not generated yet.",
    error: "Error",
    apiError: "API error",
    loadFailed: "Failed",
    compileSuccess: "Compiled",
    compileFailed: "Failed",
    outputDir: "output/",
  },
  zh: {
    statusReady: "就绪",
    statusLoading: "载入中",
    statusCompiling: "编译中",
    statusSuccess: "成功",
    statusError: "失败",
    compileBtn: "开始编译",
    loadExampleBtn: "载入示例",
    langToggle: "English",
    filenamePlaceholder: "文件名",
    sourceEditorLabel: "源代码",
    stageResultsLabel: "阶段结果",
    fullscreen: "全屏查看",
    exitFullscreen: "退出",
    copy: "复制",
    copied: "已复制",
    requestFailed: "请求失败",
    notGeneratedTokens: "尚未生成词法分析结果。",
    notGeneratedAST: "尚未生成抽象语法树。",
    notGeneratedSemantic: "尚未生成语义分析结果。",
    notGeneratedIR: "尚未生成中间代码。",
    notGeneratedASM: "尚未生成汇编代码。",
    error: "错误",
    apiError: "接口错误",
    loadFailed: "载入失败",
    compileSuccess: "编译成功",
    compileFailed: "编译失败",
    outputDir: "output/",
  },
};

const STAGE_LABELS = {
  en: {
    TOKENS: "Lexer Tokens",
    AST: "Parser AST",
    SEMANTIC: "Semantic",
    IR: "IR Code",
    ASM: "ASM Code",
    ERROR: "Error",
  },
  zh: {
    TOKENS: "词法 Tokens",
    AST: "语法 AST",
    SEMANTIC: "语义 Semantic",
    IR: "中间代码 IR",
    ASM: "汇编 ASM",
    ERROR: "错误",
  },
};

const sourceEditor = document.getElementById("source-editor");
const filenameInput = document.getElementById("filename-input");
const compileBtn = document.getElementById("compile-btn");
const loadExampleBtn = document.getElementById("load-example-btn");
const copyOutputBtn = document.getElementById("copy-output-btn");
const fullscreenBtn = document.getElementById("fullscreen-btn");
const outputPanel = document.getElementById("output-panel");
const outputViewer = document.getElementById("output-viewer");
const lineNumbers = document.getElementById("line-numbers");
const stageTabs = document.getElementById("stage-tabs");
const statusBadge = document.getElementById("status-badge");
const artifactHint = document.getElementById("artifact-hint");
const langToggleBtn = document.getElementById("lang-toggle");

let currentLang = "en";
let currentSections = {};
let currentStage = "TOKENS";

function t(key) {
  return LABELS[currentLang][key] || key;
}

function setStatus(kind, text) {
  statusBadge.className = `status-badge ${kind}`;
  statusBadge.textContent = text;
}

function setBusy(isBusy) {
  compileBtn.disabled = isBusy;
  loadExampleBtn.disabled = isBusy;
}

function updateLineNumbers() {
  const lines = Math.max(1, sourceEditor.value.split("\n").length);
  lineNumbers.textContent = Array.from({ length: lines }, (_, index) => index + 1).join("\n");
}

function renderTabs() {
  stageTabs.innerHTML = "";
  Object.keys(currentSections).forEach((key) => {
    const node = document.createElement("button");
    node.className = "stage-tab";
    node.textContent = STAGE_LABELS[currentLang][key] || key;
    node.classList.toggle("active", key === currentStage);
    node.addEventListener("click", () => {
      currentStage = key;
      renderTabs();
      renderOutput();
    });
    stageTabs.appendChild(node);
  });
}

function renderOutput() {
  outputViewer.textContent = currentSections[currentStage] || "";
}

function updateUI() {
  langToggleBtn.textContent = t("langToggle");
  statusBadge.textContent = t("statusReady");
  compileBtn.textContent = t("compileBtn");
  loadExampleBtn.textContent = t("loadExampleBtn");
  fullscreenBtn.title = t("fullscreen");
  copyOutputBtn.title = t("copy");

  const filenameSpan = filenameInput.previousElementSibling;
  if (filenameSpan) filenameSpan.textContent = t("filenamePlaceholder");

  const sourceH2 = sourceEditor.closest(".panel").querySelector("h2");
  if (sourceH2) sourceH2.textContent = t("sourceEditorLabel");

  const outputH2 = outputPanel.querySelector("h2");
  if (outputH2) outputH2.textContent = t("stageResultsLabel");

  renderTabs();
  renderOutput();
}

async function loadExample() {
  setBusy(true);
  setStatus("running", t("statusLoading"));
  try {
    const response = await fetch("/api/example");
    const payload = await response.json();
    filenameInput.value = payload.filename;
    sourceEditor.value = payload.source;
    updateLineNumbers();
    setStatus("idle", t("statusReady"));
  } finally {
    setBusy(false);
  }
}

async function compileSource() {
  const source = sourceEditor.value;
  const filename = filenameInput.value.trim() || "playground.c";

  setBusy(true);
  setStatus("running", t("statusCompiling"));
  artifactHint.textContent = "running";

  try {
    const response = await fetch("/api/compile", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ source, filename }),
    });

    const payload = await response.json();
    if (!response.ok) {
      currentSections = { ERROR: payload.error || t("requestFailed") };
      currentStage = "ERROR";
      renderTabs();
      renderOutput();
      setStatus("error", t("statusError"));
      artifactHint.textContent = "request failed";
      return;
    }

    currentSections = payload.sections || {};
    currentStage = payload.ok ? "TOKENS" : (currentSections.ERROR ? "ERROR" : "SEMANTIC");
    renderTabs();
    renderOutput();

    setStatus(payload.ok ? "success" : "error", payload.ok ? t("compileSuccess") : t("compileFailed"));
    artifactHint.textContent = payload.outputDir || t("outputDir");
  } finally {
    setBusy(false);
  }
}

async function copyCurrentOutput() {
  const text = currentSections[currentStage] || "";
  if (!text.trim()) {
    return;
  }
  await navigator.clipboard.writeText(text);
  setStatus("success", t("copied"));
}

function toggleOutputFullscreen() {
  const enabled = !outputPanel.classList.contains("fullscreen");
  outputPanel.classList.toggle("fullscreen", enabled);
  document.body.classList.toggle("output-fullscreen", enabled);
  fullscreenBtn.textContent = enabled ? t("exitFullscreen") : "⛶";
  fullscreenBtn.title = enabled ? t("exitFullscreen") : t("fullscreen");
}

compileBtn.addEventListener("click", () => {
  compileSource().catch((error) => {
    currentSections = { ERROR: String(error) };
    currentStage = "ERROR";
    renderTabs();
    renderOutput();
    setStatus("error", t("statusError"));
    artifactHint.textContent = t("apiError");
  });
});

loadExampleBtn.addEventListener("click", () => {
  loadExample().catch((error) => {
    setStatus("error", t("loadFailed"));
    artifactHint.textContent = String(error);
  });
});

copyOutputBtn.addEventListener("click", () => {
  copyCurrentOutput().catch((error) => {
    setStatus("error", t("loadFailed"));
    artifactHint.textContent = String(error);
  });
});

fullscreenBtn.addEventListener("click", toggleOutputFullscreen);

langToggleBtn.addEventListener("click", () => {
  currentLang = currentLang === "en" ? "zh" : "en";
  updateUI();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && outputPanel.classList.contains("fullscreen")) {
    toggleOutputFullscreen();
  }
});

sourceEditor.addEventListener("input", updateLineNumbers);
sourceEditor.addEventListener("scroll", () => {
  lineNumbers.scrollTop = sourceEditor.scrollTop;
});

// Initialize
currentSections = {
  TOKENS: t("notGeneratedTokens"),
  AST: t("notGeneratedAST"),
  SEMANTIC: t("notGeneratedSemantic"),
  IR: t("notGeneratedIR"),
  ASM: t("notGeneratedASM"),
};
sourceEditor.value = "";
updateLineNumbers();
updateUI();
loadExample().catch((error) => {
  setStatus("error", t("loadFailed"));
  artifactHint.textContent = String(error);
});
