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
const stageTabs = document.getElementById("stage-tabs");
const statusBadge = document.getElementById("status-badge");
const artifactHint = document.getElementById("artifact-hint");
const stageTabTemplate = document.getElementById("stage-tab-template");

let currentSections = {};
let currentStage = "TOKENS";

function setStatus(kind, text) {
  statusBadge.className = `status-badge ${kind}`;
  statusBadge.textContent = text;
}

function renderTabs() {
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
  setStatus("running", "载入中");
  const response = await fetch("/api/example");
  const payload = await response.json();
  filenameInput.value = payload.filename;
  sourceEditor.value = payload.source;
  setStatus("idle", "已载入");
}

async function compileSource() {
  const source = sourceEditor.value;
  const filename = filenameInput.value.trim() || "playground.c";

  setStatus("running", "编译中");
  artifactHint.textContent = "running";

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

currentSections = {
  TOKENS: "点击“载入示例”或直接输入源码，然后开始编译。",
  AST: "AST 将显示在这里。",
  SEMANTIC: "语义分析结果将显示在这里。",
  IR: "中间代码将显示在这里。",
  ASM: "目标汇编代码将显示在这里。",
};
renderTabs();
renderOutput();
