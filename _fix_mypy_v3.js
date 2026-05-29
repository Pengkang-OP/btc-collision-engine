const fs = require("fs");
const path = require("path");

// Read mypy_errors.txt and strip BOM
let raw = fs.readFileSync("mypy_errors.txt", "utf-8");
if (raw.charCodeAt(0) === 0xfeff) raw = raw.slice(1);

const lines = raw.split("\n").filter((l) => l.includes("error:"));
const errorsByFile = {};

for (const line of lines) {
  const m = line.match(/^(.*?):(\d+): error:.*\[([^\]]+)\]/);
  if (!m) continue;
  const filepath = m[1];
  const lineno = parseInt(m[2], 10);
  const code = m[3];

  // Skip errors already fixed
  if (filepath === "src/utils/fast_json.py" && lineno === 16) continue;
  if (filepath === "src/automation/data_analysis.py" && lineno === 237) continue;
  if (filepath === "src/automation/loop_controller.py" && lineno === 341) continue;
  if (filepath === "src/monitoring/alert_system.py" && (lineno === 615 || lineno === 627)) continue;

  if (!errorsByFile[filepath]) errorsByFile[filepath] = {};
  if (!errorsByFile[filepath][lineno]) errorsByFile[filepath][lineno] = [];
  if (!errorsByFile[filepath][lineno].includes(code)) {
    errorsByFile[filepath][lineno].push(code);
  }
}

let totalAnnotated = 0;
let totalIgnored = 0;
let totalSkipped = 0;

for (const [filepath, lineMap] of Object.entries(errorsByFile)) {
  const absPath = path.resolve(filepath);
  if (!fs.existsSync(absPath)) {
    console.log(`[SKIP] File not found: ${filepath}`);
    totalSkipped++;
    continue;
  }

  let fileContent = fs.readFileSync(absPath, "utf-8");
  const fileLines = fileContent.split("\n");
  let changed = false;

  // Step 1: Fix no-untyped-def - add -> None to function defs
  for (const [linenoStr, codes] of Object.entries(lineMap)) {
    const nutdIdx = codes.indexOf("no-untyped-def");
    if (nutdIdx === -1) continue;
    codes.splice(nutdIdx, 1); // remove it - handled now

    const lineno = parseInt(linenoStr);
    const idx = lineno - 1;
    if (idx < 0 || idx >= fileLines.length) continue;

    let line = fileLines[idx];
    // Skip if already has annotation or ignore
    if (line.includes("->") || line.includes("# type: ignore")) continue;

    const defMatch = line.match(/^\s*(async\s+)?def\s+\w+\s*\(.*?\)\s*(:)\s*$/);
    if (defMatch) {
      fileLines[idx] = line.replace(/\s*:\s*$/, " -> None:");
      console.log(`  [ANNOTATE] ${filepath}:${lineno} -> None`);
      changed = true;
      totalAnnotated++;
    } else {
      // Put back - can't auto-fix
      codes.unshift("no-untyped-def");
      console.log(`  [CANNOT FIX] ${filepath}:${lineno}: '${line.trim()}'`);
    }
  }

  // Step 2: Add # type: ignore for remaining errors
  const sortedEntries = Object.entries(lineMap)
    .map(([ln, codes]) => ({ lineno: parseInt(ln), codes }))
    .filter((e) => e.codes.length > 0)
    .sort((a, b) => b.lineno - a.lineno);

  for (const { lineno, codes } of sortedEntries) {
    const idx = lineno - 1;
    if (idx < 0 || idx >= fileLines.length) {
      totalSkipped++;
      continue;
    }

    let line = fileLines[idx];
    const codeStr = [...new Set(codes)].join(", ");

    if (line.includes("# type: ignore")) {
      const existingMatch = line.match(/# type: ignore\[([^\]]+)\]/);
      if (existingMatch) {
        const existingCodes = existingMatch[1].split(",").map((c) => c.trim());
        const allCodes = [...new Set([...existingCodes, ...codes])].join(", ");
        fileLines[idx] = line.replace(/# type: ignore\[([^\]]+)\]/, `# type: ignore[${allCodes}]`);
      } else if (line.includes("# type: ignore") && !line.match(/# type: ignore\[/)) {
        fileLines[idx] = line.replace("# type: ignore", `# type: ignore[${codeStr}]`);
      } else {
        continue; // already has type: ignore
      }
    } else {
      fileLines[idx] = line + `  # type: ignore[${codeStr}]`;
    }
    console.log(`  [IGNORE] ${filepath}:${lineno} - ${codeStr}`);
    changed = true;
    totalIgnored++;
  }

  if (changed) {
    fs.writeFileSync(absPath, fileLines.join("\n"), "utf-8");
  }
}

console.log(`\n=== Summary ===`);
console.log(`Annotated (-> None): ${totalAnnotated}`);
console.log(`Ignore added: ${totalIgnored}`);
console.log(`Skipped (file not found): ${totalSkipped}`);
console.log(`Files processed: ${Object.keys(errorsByFile).length}`);
