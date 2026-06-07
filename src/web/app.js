// 前端交互脚本：负责载入示例、提交源码、切换阶段输出。
const STAGE_LABELS = {
  TOKENS: "TOKENS",
  AST: "AST",
  SEMANTIC: "SEMANTIC",
  IR: "IR",
  ASM: "ASM",
  ERROR: "ERROR",
};

const sourceEditor = document.getElementById("source-editor");
const filenameInput = document.getElementById("filename-input");
const compileBtn = document.getElementById("compile-btn");
const loadExampleBtn = document.getElementById("load-example-btn");
const outputViewer = document.getElementById("output-viewer");
const lineNumbers = document.getElementById("line-numbers");
const stageTabs = document.getElementById("stage-tabs");
const statusBadge = document.getElementById("status-badge");
const artifactHint = document.getElementById("artifact-hint");
const stageTabTemplate = document.getElementById("stage-tab-template");

let currentSections = {};
let currentStage = "TOKENS";

function setStatus(kind, text) {
  // kind 对应 CSS 中的 idle/running/success/error 状态。
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
  // 根据后端返回的阶段列表动态生成标签页。
  stageTabs.innerHTML = "";
  Object.keys(currentSections).forEach((key) => {
    const node = stageTabTemplate.content.firstElementChild.cloneNode(true);
    node.textContent = STAGE_LABELS[key] || key;
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

async function loadExample() {
  setBusy(true);
  setStatus("running", "载入中");
  try {
    const response = await fetch("/api/example");
    const payload = await response.json();
    filenameInput.value = payload.filename;
    sourceEditor.value = payload.source;
    updateLineNumbers();
    setStatus("idle", "已载入");
  } finally {
    setBusy(false);
  }
}

async function compileSource() {
  // 将当前编辑器内容提交给本地后端，由 Python 编译器完成分析。
  const source = sourceEditor.value;
  const filename = filenameInput.value.trim() || "playground.c";

  setBusy(true);
  setStatus("running", "编译中");
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
      currentSections = { ERROR: payload.error || "请求失败" };
      currentStage = "ERROR";
      renderTabs();
      renderOutput();
      setStatus("error", "失败");
      artifactHint.textContent = "request failed";
      return;
    }

    currentSections = payload.sections || {};
    currentStage = payload.ok ? "TOKENS" : (currentSections.ERROR ? "ERROR" : "SEMANTIC");
    renderTabs();
    renderOutput();

    setStatus(payload.ok ? "success" : "error", payload.ok ? "编译成功" : "编译失败");
    artifactHint.textContent = payload.outputDir || "output/";
  } finally {
    setBusy(false);
  }
}

compileBtn.addEventListener("click", () => {
  compileSource().catch((error) => {
    currentSections = { ERROR: String(error) };
    currentStage = "ERROR";
    renderTabs();
    renderOutput();
    setStatus("error", "异常");
    artifactHint.textContent = "api error";
  });
});

loadExampleBtn.addEventListener("click", () => {
  loadExample().catch((error) => {
    setStatus("error", "失败");
    artifactHint.textContent = String(error);
  });
});

sourceEditor.addEventListener("input", updateLineNumbers);
sourceEditor.addEventListener("scroll", () => {
  lineNumbers.scrollTop = sourceEditor.scrollTop;
});

currentSections = {
  TOKENS: "尚未生成词法分析结果。",
  AST: "尚未生成抽象语法树。",
  SEMANTIC: "尚未生成语义分析结果。",
  IR: "尚未生成中间代码。",
  ASM: "尚未生成汇编代码。",
};
sourceEditor.value = "";
updateLineNumbers();
renderTabs();
renderOutput();
loadExample().catch((error) => {
  setStatus("error", "失败");
  artifactHint.textContent = String(error);
});
