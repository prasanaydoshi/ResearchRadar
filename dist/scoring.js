/* Portable scoring; intentionally mirrors radar/model.py. No eval or model binaries. */
(function (root) {
  'use strict';
  function tokenize(title) { return title.toLowerCase().match(/[a-z0-9]{2,}/g) || []; }
  function predict(model, paper) {
    const counts = new Map();
    for (const t of tokenize(paper.title)) counts.set(t, (counts.get(t) || 0) + 1);
    const tfidf = [...counts].filter(([t]) => Object.hasOwn(model.idf, t)).map(([t, c]) => [t, c * model.idf[t]]);
    const norm = Math.sqrt(tfidf.reduce((s, [, v]) => s + v * v, 0)) || 1;
    const parts = tfidf.map(([t, v]) => ({feature: t, log_odds: v / norm * model.text_weights[t]}));
    const numeric = [paper.author_count || 0, paper.reference_count || 0, tokenize(paper.title).length, paper.sampled_author_history || 0, paper.sampled_reference_links || 0];
    numeric.forEach((v, i) => parts.push({feature: model.feature_names[i], log_odds: (Math.log1p(Math.max(0, v)) - model.means[i]) / model.scales[i] * model.numeric_weights[i]}));
    const raw = model.intercept + parts.reduce((s, p) => s + p.log_odds, 0);
    const calibrated = model.calibration.slope * raw + model.calibration.intercept;
    return {probability: 1 / (1 + Math.exp(-Math.max(-35, Math.min(35, calibrated)))), contributions: parts.sort((a, b) => Math.abs(b.log_odds) - Math.abs(a.log_odds)).slice(0, 6)};
  }
  if (typeof module !== 'undefined') module.exports = {predict};
  else root.RadarScoring = {predict};
})(typeof window !== 'undefined' ? window : this);
