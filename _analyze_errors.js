const fs = require("fs");
const content = fs.readFileSync("mypy_errors.txt", "utf-8");
const lines = content.split("\n").filter((l) => l.includes("error:"));
const codes = {};
const files = {};
for (const line of lines) {
  const cm = line.match(/\[([^\]]+)\]\s*$/);
  if (cm) codes[cm[1]] = (codes[cm[1]] || 0) + 1;
  const fm = line.match(/^[^:]*src\/([^:]+)/);
  if (fm) files[fm[1]] = (files[fm[1]] || 0) + 1;
}
console.log("=== Error Codes ===");
Object.entries(codes)
  .sort((a, b) => b[1] - a[1])
  .forEach(([k, v]) => console.log(k + ":", v));
console.log("\nTotal:", Object.values(codes).reduce((a, b) => a + b, 0));
console.log("\n=== Files ===");
Object.entries(files)
  .sort((a, b) => b[1] - a[1])
  .forEach(([k, v]) => console.log(k + ":", v));
