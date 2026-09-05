const fs = require('node:fs');
const assert = require('node:assert/strict');
const {predict} = require('../dist/scoring.js');
const model = JSON.parse(fs.readFileSync('dist/model.json'));
const papers = JSON.parse(fs.readFileSync('dist/papers.json'));
for (const p of papers) {
  const actual = predict(model, p).probability;
  assert.ok(Math.abs(actual - p.probability) < 1e-10, `${p.id}: ${actual} versus ${p.probability}`);
}
for (const title of ['__proto__ constructor toString', '<script>alert(1)</script>', '学习机器人 neural networks', '']) {
  const result = predict(model, {title, author_count: 1, reference_count: 10});
  assert.ok(Number.isFinite(result.probability));
  assert.ok(result.probability >= 0 && result.probability <= 1);
}
console.log(`Portable JavaScript agrees with Python for all ${papers.length} real papers; edge cases passed.`);
