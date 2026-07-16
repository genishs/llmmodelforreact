/*
 * score_v2_extract.cjs — TypeScript-compiler front-end for scripts/score_v2.py (하니스 v2).
 *
 * 순수 "사실 추출기": 모델 미적재·GPU 0. 저장된 생성물(.tsx)과 원본(.jsx)을 TS 컴파일러 API로
 * 파싱해 채점에 필요한 "사실"만 뽑아 stdout(JSON)으로 넘긴다. 점수 산술은 전부 score_v2.py에.
 *
 * 왜 Node인가: 현행 정규식 `TS1\d{3}$` 는 구문에러 TS17008(JSX 미닫힘, 5자리)을 놓친다(실측).
 * 대신 program.getSyntacticDiagnostics()(=parseDiagnostics, 억제 없음) vs getSemanticDiagnostics()로
 * 구문/타입을 컴파일러 자체 분류에 맡긴다.
 *
 * 입력(argv[2]=JSON 파일 경로):
 *   { "tsconfig": "<abs tsconfig.json>", "shims": "<abs shims.d.ts>",
 *     "files": [ { "task": "...", "label": "...", "gen": "<abs .tsx>", "src": "<abs .jsx>|null" }, ... ] }
 * 출력(stdout, JSON): { "ts_version": "..", "results": [ { per-file facts } ] }
 *
 * per-file facts:
 *   file_len   : gen 소스 길이(UTF-16 code unit — TS diagnostic .start 와 동일 단위)
 *   syn        : 구문 진단 [{code,start}]  (getSyntacticDiagnostics, 억제 없음)
 *   sem        : 타입 진단 코드 배열 [int]  (getSemanticDiagnostics, TS2347 전역제외 — 샌드박스 스텁 아티팩트)
 *   syn_first  : 첫 구문진단 .start (없으면 null)
 *   gen_idents : gen 식별자 텍스트 배열(중복 포함)
 *   gen_jsx    : gen JSX 여는/셀프클로징 태그명 배열(중복 포함)
 *   src_idents : 원본 .jsx 식별자 배열(없으면 null)
 *   src_jsx    : 원본 .jsx JSX 태그명 배열(없으면 null)
 */
"use strict";
const path = require("path");
const fs = require("fs");
const ts = require(path.join(__dirname, "..", "node_modules", "typescript"));

const TS2347_EXCLUDE = 2347; // 샌드박스 스텁 lib의 any<T>() 명시적 타입인자 = 아티팩트(v1 합의와 동일)

function loadOptions(tsconfigPath) {
  const raw = ts.readConfigFile(tsconfigPath, ts.sys.readFile);
  if (raw.error) throw new Error("tsconfig read fail: " + JSON.stringify(raw.error));
  const parsed = ts.parseJsonConfigFileContent(
    raw.config, ts.sys, path.dirname(tsconfigPath));
  return parsed.options;
}

// AST 워크: 식별자 + JSX 태그명 수집 (order-deterministic).
function collect(sourceFile) {
  const idents = [];
  const jsx = [];
  const text = sourceFile.text;
  function tagText(el) {
    const tn = el.tagName;
    return text.substring(tn.pos, tn.end).trim();
  }
  function walk(node) {
    if (node.kind === ts.SyntaxKind.Identifier) {
      idents.push(node.escapedText !== undefined ? String(node.escapedText) : node.getText(sourceFile));
    } else if (node.kind === ts.SyntaxKind.JsxOpeningElement ||
               node.kind === ts.SyntaxKind.JsxSelfClosingElement) {
      jsx.push(tagText(node));
    }
    ts.forEachChild(node, walk);
  }
  walk(sourceFile);
  return { idents, jsx };
}

function main() {
  const manifestPath = process.argv[2];
  if (!manifestPath) { console.error("usage: node score_v2_extract.cjs <manifest.json>"); process.exit(2); }
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  const options = loadOptions(manifest.tsconfig);
  const shims = manifest.shims;

  const results = [];
  for (const f of manifest.files) {
    const genText = fs.readFileSync(f.gen, "utf8");
    // 파일별 단독 프로그램(현행 하니스의 per-file 격리와 동일 — declare module '*' 상호간섭 제거).
    const program = ts.createProgram({ rootNames: [f.gen, shims], options });
    const sf = program.getSourceFile(f.gen);
    const synDiags = program.getSyntacticDiagnostics(sf);
    const semDiags = program.getSemanticDiagnostics(sf)
      .filter(d => d.code !== TS2347_EXCLUDE);

    const syn = synDiags.map(d => ({ code: d.code, start: (d.start == null ? -1 : d.start) }));
    const sem = semDiags.map(d => d.code);
    let synFirst = null;
    for (const s of syn) { if (s.start >= 0 && (synFirst === null || s.start < synFirst)) synFirst = s.start; }

    const genC = collect(sf);
    let srcC = { idents: null, jsx: null };
    if (f.src) {
      const srcText = fs.readFileSync(f.src, "utf8").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
      const srcSf = ts.createSourceFile(
        path.basename(f.src), srcText, ts.ScriptTarget.ES2020, true, ts.ScriptKind.JSX);
      srcC = collect(srcSf);
    }

    results.push({
      task: f.task, label: f.label,
      file_len: genText.length,
      syn, sem, syn_first: synFirst,
      gen_idents: genC.idents, gen_jsx: genC.jsx,
      src_idents: srcC.idents, src_jsx: srcC.jsx,
    });
  }
  process.stdout.write(JSON.stringify({ ts_version: ts.version, results }));
}

main();
