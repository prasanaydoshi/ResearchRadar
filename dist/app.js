'use strict';
const $ = id => document.getElementById(id);
const percent = n => `${(n * 100).toFixed(1)}%`;
const number = n => n == null ? '—' : n.toFixed(3);
let corpus = [], model, evaluation, visible = [], limit = 20, revealed = false, saved = new Set();
try { const s = JSON.parse(localStorage.getItem('radar-reading-list') || '[]'); if (Array.isArray(s)) saved = new Set(s.filter(v => typeof v === 'string')); } catch (_) { /* private browsing or damaged preferences */ }
function node(tag, text, className) { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (className) n.className = className; return n; }
function link(label, url) { const n = node('a', label); try { const u = new URL(url); if (u.protocol === 'https:') { n.href = u.href; n.target = '_blank'; n.rel = 'noopener noreferrer'; } } catch (_) {} return n; }
function savePaper(id, button) { if (saved.has(id)) saved.delete(id); else saved.add(id); try {localStorage.setItem('radar-reading-list', JSON.stringify([...saved]));} catch (_) {} button.textContent = saved.has(id) ? 'Saved ✓' : 'Save +'; button.setAttribute('aria-pressed', String(saved.has(id))); if ($('saved-only').checked) render(); }
function explain(paper, element) {
  element.append(node('h3', 'Why this score?'));
  for (const p of paper.contributions) {
    const row = node('div', undefined, 'contribution');
    row.append(node('span', p.feature.replaceAll('_', ' ')), node('strong', `${p.log_odds > 0 ? '+' : ''}${p.log_odds.toFixed(2)}`, p.log_odds >= 0 ? 'positive' : 'negative'));
    element.append(row);
  }
  element.append(node('p', 'Contributions are additive log-odds before calibration, relative to average metadata. Associations do not explain scientific merit.', 'fineprint'));
}
function detail(paper) {
  const e = $('detail-content'); e.replaceChildren(node('p', paper.topic, 'eyebrow'), node('h2', paper.title), node('p', `${paper.authors.join(', ')} · ${paper.publication_date}`), node('div', percent(paper.probability), 'big-score'));
  e.append(node('p', 'Estimated chance of top-decile citation attention in the sampled cohort.'));
  explain(paper, e);
  if (revealed && paper.outcome) e.append(node('p', `Observed: ${paper.outcome.target_citations} citations in ${paper.outcome.target_year}. Cohort threshold: ${paper.outcome.threshold}. ${paper.outcome.target ? 'Reached top decile.' : 'Below top decile.'}`, 'outcome'));
  e.append(link('Read paper ↗', paper.doi || paper.id)); $('detail').showModal();
}
function card(paper, index, isLive = false) {
  const article = node('article', undefined, 'paper');
  const rank = node('div', String(index + 1).padStart(2, '0'), 'rank');
  const info = node('div', undefined, 'paper-info');
  info.append(node('p', `${paper.topic} · ${paper.publication_date}`, 'metadata'));
  const title = node('button', paper.title, 'paper-title'); title.onclick = () => detail(paper);
  info.append(title, node('p', `${paper.authors.slice(0, 3).join(', ')}${paper.authors.length > 3 ? ' et al.' : ''}`, 'authors'));
  if (revealed && paper.outcome && !isLive) info.append(node('p', `${paper.outcome.target ? 'TOP DECILE' : 'BELOW THRESHOLD'} · ${paper.outcome.target_citations} citations in ${paper.outcome.target_year} · threshold ${paper.outcome.threshold}`, `outcome ${paper.outcome.target ? 'success' : ''}`));
  const actions = node('div', undefined, 'paper-actions'); const score = node('button', percent(paper.probability), 'score'); score.setAttribute('aria-label', `${percent(paper.probability)} estimated attention probability. Inspect score.`); score.onclick = () => detail(paper);
  const save = node('button', saved.has(paper.id) ? 'Saved ✓' : 'Save +', 'save'); save.setAttribute('aria-pressed', String(saved.has(paper.id))); save.onclick = () => savePaper(paper.id, save);
  actions.append(score, node('span', 'attention estimate', 'metadata'), save);
  article.append(rank, info, actions); return article;
}
function render() {
  const q = $('query').value.trim().toLowerCase(), year = Number($('year').value);
  visible = corpus.filter(p => p.split === 'test' && p.publication_year === year && (p.title.toLowerCase().includes(q) || p.topic.toLowerCase().includes(q)) && (!$('saved-only').checked || saved.has(p.id)));
  visible.sort($('sort').value === 'probability' ? (a,b) => b.probability - a.probability || a.id.localeCompare(b.id) : (a,b) => b.publication_date.localeCompare(a.publication_date));
  $('papers').replaceChildren(...visible.slice(0, limit).map((p, i) => card(p, i)));
  if (!visible.length) $('papers').append(node('p', 'No papers match these filters. Try another topic, year, or reading-list setting.', 'empty'));
  $('cohort-context').textContent = `${year} held-out cohort · model ready ${evaluation.model_ready_date} · ${revealed ? `outcomes from ${year + 1} revealed` : 'future citation outcomes hidden'}`;
  $('more').hidden = visible.length <= limit;
  $('result-count').textContent = `${Math.min(limit, visible.length)} of ${visible.length} papers`;
  $('reveal').textContent = revealed ? 'Hide future outcomes' : 'Reveal future outcomes';
}
function renderEvidence() {
  $('target-description').textContent = evaluation.target;
  $('limitations').replaceChildren(...evaluation.limitations.map(x => node('li', x)));
  const stages = [[`Train / ${evaluation.train_years.join('–')}`, evaluation.train_n], [`Calibrate / ${evaluation.calibration_year}`, evaluation.calibration_n], [`Test / ${evaluation.test_years.join('–')}`, evaluation.test_n]];
  $('split-timeline').replaceChildren(...stages.map(([title, n]) => {const box = node('div'); box.append(node('p', title), node('strong', `${n.toLocaleString()} papers`)); return box;}));
  $('metrics').replaceChildren(...[['Title + metadata + graph', 'full_model'], ['Metadata + graph baseline', 'metadata_baseline'], ['Title-only ablation', 'title_only_ablation'], ['Constant prevalence baseline', 'constant_baseline']].map(([name, key]) => {const tr = node('tr'), m = evaluation[key]; tr.append(node('th', name), node('td', percent(m.precision_at_20)), node('td', number(m.ndcg_at_20)), node('td', number(m.average_precision)), node('td', number(m.brier))); return tr;}));
  const svg = $('calibration'), ns = 'http://www.w3.org/2000/svg';
  const add = (tag, attrs, text) => {const e = document.createElementNS(ns, tag); for (const [k,v] of Object.entries(attrs)) e.setAttribute(k, String(v)); if (text) e.textContent = text; svg.append(e);};
  add('line', {x1:45,y1:260,x2:375,y2:30,stroke:'#75849c','stroke-dasharray':'5 5'});
  add('line', {x1:45,y1:260,x2:375,y2:260,stroke:'#53617a'}); add('line',{x1:45,y1:260,x2:45,y2:30,stroke:'#53617a'});
  for(let i=0;i<=4;i++){add('text',{x:45+i*82.5,y:282,fill:'#99a9c2','font-size':13,'text-anchor':'middle'},`${i*25}%`); add('text',{x:35,y:264-i*57.5,fill:'#99a9c2','font-size':13,'text-anchor':'end'},`${i*25}%`);}
  for(const bin of evaluation.full_model.reliability_bins) {const dot = document.createElementNS(ns,'circle'); dot.setAttribute('cx',String(45+330*bin.predicted));dot.setAttribute('cy',String(260-230*bin.observed));dot.setAttribute('r',String(Math.min(13, 4+Math.sqrt(bin.n)/3)));dot.setAttribute('fill','#7af0d0');const title=document.createElementNS(ns,'title');title.textContent=`${bin.n} papers: predicted ${percent(bin.predicted)}, observed ${percent(bin.observed)}`;dot.append(title);svg.append(dot);}
  add('text',{x:210,y:308,fill:'#99a9c2','font-size':14,'text-anchor':'middle'},'Predicted probability');
}
document.querySelectorAll('.tab').forEach(button => button.onclick = () => {document.querySelectorAll('.tab').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!==button.dataset.view);});
['year','query','sort','saved-only'].forEach(id => $(id).addEventListener('input',()=>{limit=20; render();}));
$('reveal').onclick=()=>{revealed=!revealed;render();};$('more').onclick=()=>{limit+=20;render();};$('close-detail').onclick=()=>$('detail').close();
$('export').onclick=()=>{const data = visible.map(p=>{const r={...p};if(!revealed)delete r.outcome;return r;});const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=node('a');a.href=url;a.download='research-radar-reading-list.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('score-form').onsubmit=e=>{e.preventDefault();if(!model)return;const paper={title:$('paper-title').value,author_count:Number($('author-count').value),reference_count:Number($('reference-count').value)};const result=RadarScoring.predict(model,paper);const target=$('score-output');target.replaceChildren(node('p','ESTIMATED ATTENTION','eyebrow'),node('div',percent(result.probability),'big-score'),node('p','Estimated chance of entering the sampled cohort’s top citation decile.'));explain(result,target);};
$('live-form').onsubmit=async e=>{e.preventDefault();$('live-status').textContent='Searching OpenAlex…';$('live-results').replaceChildren();try{const response=await fetch(`/api/search?q=${encodeURIComponent($('live-query').value)}&year=${$('live-year').value}`);if(!response.ok)throw Error('Live search requires the included Python API server and working OpenAlex access.');const data=await response.json();$('live-status').textContent=data.warning;$('live-results').replaceChildren(...data.papers.map((p,i)=>card(p,i,true)));if(!data.papers.length)$('live-status').textContent='No matching papers found for this year.';}catch(err){$('live-status').textContent=err.message;}};
Promise.all(['papers','model','evaluation'].map(async name=>{const r=await fetch(`${name}.json`);if(!r.ok)throw Error(`Cannot load ${name}.json. Serve the dist folder over HTTP or run the included Python server.`);return r.json();})).then(([papers,m,e])=>{corpus=papers;model=m;evaluation=e;$('sample-count').textContent=e.sample_size.toLocaleString();$('year').replaceChildren(...e.test_years.map(y=>{const option=node('option',String(y));option.value=String(y);return option;}));$('loading').hidden=true;render();renderEvidence();}).catch(err=>{$('loading').hidden=true;$('error').hidden=false;$('error').textContent=err.message;});
