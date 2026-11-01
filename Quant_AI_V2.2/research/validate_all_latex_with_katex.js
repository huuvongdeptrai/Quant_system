const fs = require('fs');
const path = require('path');
const katex = require(process.env.APPDATA + '/npm/node_modules/katex');

const thesisDir = path.resolve('Kho_Do_An/Quant_AI_V2.2/docs/thesis');
const files = fs.readdirSync(thesisDir).filter(f => f.endsWith('.md'));

let totalErrors = 0;
let totalBlocks = 0;

for (const file of files) {
  const filePath = path.join(thesisDir, file);
  const content = fs.readFileSync(filePath, 'utf-8');

  // Strip code blocks ``` ... ```
  const withoutCode = content.replace(/```[\s\S]*?```/g, m => ' '.repeat(m.length));

  let fileErrors = [];

  // 1. Test Display Math $$ ... $$
  const displayRegex = /\$\$([\s\S]*?)\$\$/g;
  let match;
  while ((match = displayRegex.exec(withoutCode)) !== null) {
    totalBlocks++;
    const math = match[1];
    const lineNo = content.substring(0, match.index).split('\n').length;
    try {
      katex.renderToString(math, { displayMode: true, throwOnError: true, strict: 'ignore' });
    } catch (err) {
      fileErrors.push({ type: 'DISPLAY', lineNo, msg: err.message, math: math.trim().substring(0, 100).replace(/\n/g, ' ') });
      totalErrors++;
    }
  }

  // 2. Test Inline Math $ ... $
  const withoutDisplay = withoutCode.replace(/\$\$[\s\S]*?\$\$/g, m => ' '.repeat(m.length));
  const inlineRegex = /(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)/g;
  while ((match = inlineRegex.exec(withoutDisplay)) !== null) {
    totalBlocks++;
    const math = match[1];
    if (!math.trim()) continue;
    // Skip if it looks like price like $100 or currency outside math
    if (/^\s*[\d,]+(\.\d+)?\s*(USD|VND|points|lot|lots|%|$)/.test(math)) continue;
    const lineNo = content.substring(0, match.index).split('\n').length;
    try {
      katex.renderToString(math, { displayMode: false, throwOnError: true, strict: 'ignore' });
    } catch (err) {
      fileErrors.push({ type: 'INLINE', lineNo, msg: err.message, math: math.trim() });
      totalErrors++;
    }
  }

  if (fileErrors.length > 0) {
    console.log(`\n=== ${file} (${fileErrors.length} ERRORS) ===`);
    for (const e of fileErrors) {
      console.log(`  [${e.type} Line ${e.lineNo}]: ${e.msg}`);
      console.log(`    Snippet: ${e.math}`);
    }
  } else {
    console.log(`${file}: 0 KaTeX errors.`);
  }
}

console.log(`\n===========================================`);
console.log(`Tested ${totalBlocks} math blocks. Total KaTeX render errors: ${totalErrors}`);
console.log(`===========================================`);
