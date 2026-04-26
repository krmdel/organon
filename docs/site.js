(function () {
  'use strict';

  const body = document.getElementById('term-body');
  const replayBtn = document.getElementById('replay-btn');
  const termTitle = document.getElementById('term-title');
  const tabs = Array.from(document.querySelectorAll('.demo-tab'));
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const ABORTED = Symbol('aborted');
  let currentToken = { aborted: false };
  let currentScript = 'literature';

  function newRun() {
    currentToken.aborted = true;
    currentToken = { aborted: false };
    return currentToken;
  }

  function sleep(ms, token) {
    return new Promise((resolve, reject) => {
      if (token.aborted) return reject(ABORTED);
      const effective = prefersReduced ? Math.min(ms, 120) : ms;
      setTimeout(() => {
        if (token.aborted) return reject(ABORTED);
        resolve();
      }, effective);
    });
  }

  function appendDiv() {
    const div = document.createElement('div');
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
    return div;
  }

  async function typeInto(el, text, delay, token) {
    if (prefersReduced) {
      el.textContent = text;
      body.scrollTop = body.scrollHeight;
      return;
    }
    for (const ch of text) {
      if (token.aborted) throw ABORTED;
      el.textContent += ch;
      body.scrollTop = body.scrollHeight;
      await sleep(delay + Math.random() * 25, token);
    }
  }

  async function typeLine(token, { prompt = null, text = '', speed = 42, pauseAfter = 500 }) {
    const line = appendDiv();
    if (prompt) {
      const p = document.createElement('span');
      p.className = 'prompt';
      p.textContent = prompt + ' ';
      line.appendChild(p);
    }
    const content = document.createElement('span');
    content.className = 'user-input';
    line.appendChild(content);
    await typeInto(content, text, speed, token);
    await sleep(pauseAfter, token);
  }

  async function printHTML(token, html, pauseAfter = 100) {
    if (token.aborted) throw ABORTED;
    const div = appendDiv();
    div.innerHTML = html;
    await sleep(pauseAfter, token);
  }

  async function spinner(token, label, duration = 1800) {
    const frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
    const line = appendDiv();
    const spin = document.createElement('span');
    spin.className = 'tool';
    const rest = document.createElement('span');
    rest.className = 'muted';
    rest.textContent = '  ' + label;
    line.appendChild(spin);
    line.appendChild(rest);

    if (prefersReduced) {
      spin.textContent = '  ⠿';
      await sleep(200, token);
    } else {
      const start = Date.now();
      let i = 0;
      while (Date.now() - start < duration) {
        if (token.aborted) throw ABORTED;
        spin.textContent = '  ' + frames[i++ % frames.length];
        await sleep(90, token);
      }
    }
    return line;
  }

  async function routeHeader(token, { skill, trigger, reason }) {
    await printHTML(token, '&nbsp;', 60);
    await printHTML(token, '<span class="route-header">--- SKILL ROUTED ---</span>', 150);
    await printHTML(token, `<span class="route-label">Skill:</span>   <span class="success">${skill}</span>`, 70);
    await printHTML(token, `<span class="route-label">Trigger:</span> <span class="muted">"${trigger}"</span>`, 70);
    await printHTML(token, `<span class="route-label">Reason:</span>  <span class="muted">${reason}</span>`, 70);
    await printHTML(token, '<span class="route-header">---</span>', 320);
    await printHTML(token, '&nbsp;', 80);
  }

  function clearBody() {
    body.innerHTML = '';
  }

  // ─── SCRIPTS ──────────────────────────────────────────────────────────

  async function runLiterature(token) {
    await typeLine(token, {
      prompt: '>',
      text: 'latest AI drug discovery research',
      speed: 44,
      pauseAfter: 600,
    });
    await routeHeader(token, {
      skill: 'sci-literature-research',
      trigger: 'latest … research',
      reason: 'discovery query — federated PubMed + arXiv + OpenAlex + S2',
    });
    await printHTML(
      token,
      '<span class="tool">→</span> <span class="muted">paper-search.search_papers(query=</span><span class="user-input">"artificial intelligence drug discovery"</span><span class="muted">, date=</span><span class="user-input">"2025-01-01:"</span><span class="muted">)</span>',
      120
    );
    const spin = await spinner(token, 'searching PubMed, arXiv, OpenAlex, Semantic Scholar…', 2200);
    spin.innerHTML = '<span class="success">  ✓</span>  <span class="muted">24 results across 4 sources</span>';
    await sleep(500, token);

    await printHTML(token, '&nbsp;', 120);
    await printHTML(token, '<span class="sep-line">── Top results ──────────────────────────────────────</span>', 240);
    await printHTML(token, '&nbsp;', 60);

    const papers = [
      { n: 1, title: 'AI Will Accelerate Drug Discovery by Accelerating Clinical Evidence',
        authors: 'Baicker, Obermeyer', journal: 'JAMA Health Forum', year: '2026',
        cites: null, doi: '10.1001/jamahealthforum.2026.1596' },
      { n: 2, title: 'Integrating AI in drug discovery and early drug development',
        authors: 'Ocaña, Pandiella, Privat, …, Győrffy', journal: 'Biomarker Research', year: '2025',
        cites: 108, doi: '10.1186/s40364-025-00758-2' },
      { n: 3, title: 'AI for Predicting Small-Molecule Bioactive Conformations',
        authors: 'Liu, Chen, Lin, Gao, Li', journal: 'J. Chem. Inf. Model.', year: '2026',
        cites: null, doi: '10.1021/acs.jcim.5c03198' },
      { n: 4, title: 'Role of AI in Cancer Drug Discovery and Development',
        authors: 'Sarvepalli, Vadarevu', journal: 'Cancer Letters', year: '2025',
        cites: 32, doi: '10.1016/j.canlet.2025.217821' },
      { n: 5, title: 'From Lab to Clinic: How AI Is Reshaping Drug Discovery Timelines',
        authors: 'Dermawan, Alotaiq', journal: 'Pharmaceuticals', year: '2025',
        cites: 15, doi: '10.3390/ph18070981' },
    ];

    for (const p of papers) {
      const citeStr = p.cites ? ` · ${p.cites} citations` : '';
      await printHTML(token, `<span class="paper-title">[${p.n}] ${p.title}</span>`, 120);
      await printHTML(
        token,
        `     <span class="paper-meta">${p.authors}</span> <span class="muted">·</span> <span class="paper-journal">${p.journal}, ${p.year}</span><span class="paper-meta">${citeStr}</span>`,
        60
      );
      await printHTML(token, `     <span class="muted">doi:</span> <span class="doi">${p.doi}</span>`, 60);
      await printHTML(token, '&nbsp;', 130);
    }

    await printHTML(token, '<span class="sep-line">─────────────────────────────────────────────────────</span>', 240);
    await printHTML(
      token,
      '<span class="success">✓ Saved to</span> <span class="muted">projects/sci-literature-research/2026-04-18_ai-drug-discovery.md</span>',
      360
    );
    await printHTML(token, '<span class="muted">↳ opened in editor · BibTeX exported · Push to Drive? (y/n)</span>', 200);
  }

  async function runHypothesis(token) {
    await typeLine(token, {
      prompt: '>',
      text: 'from these 5 papers, whats a testable hypothesis?',
      speed: 44,
      pauseAfter: 600,
    });
    await routeHeader(token, {
      skill: 'sci-hypothesis',
      trigger: 'testable hypothesis',
      reason: 'hypothesis generation — grounded in just-loaded literature',
    });

    await printHTML(token, '<span class="tool">→</span> <span class="muted">reading research-profile.md + 2026-04-18_ai-drug-discovery.md</span>', 140);
    await printHTML(token, '  <span class="success">✓</span> <span class="muted">profile: computational biology · small-molecule design · PyTorch</span>', 90);
    await printHTML(token, '  <span class="success">✓</span> <span class="muted">5 papers loaded · 24 candidate mechanisms extracted</span>', 120);
    await printHTML(token, '&nbsp;', 100);

    await printHTML(token, '<span class="sep-line">── Generated hypotheses (ranked by novelty × testability) ──</span>', 240);
    await printHTML(token, '&nbsp;', 60);

    // H1
    await printHTML(token, '<span class="paper-title">[H1]</span> <span class="key">novelty</span> <span class="num">0.82</span>  <span class="key">testability</span> <span class="num">0.91</span>', 160);
    await printHTML(token, '     <span class="muted">Claim:</span> diffusion-based bioactive-conformation models trained on', 80);
    await printHTML(token, '            ligand-pocket pairs outperform equilibrium-sampling on', 80);
    await printHTML(token, '            flexible kinases (RMSD &lt; 1.5 Å) but not on rigid GPCRs.', 80);
    await printHTML(token, '     <span class="muted">Support:</span> <span class="doi">[3]</span> Liu et al. 2026 · <span class="doi">[2]</span> Ocaña et al. 2025', 80);
    await printHTML(token, '     <span class="muted">Design:</span>  12 kinase + 12 GPCR targets · matched-pair', 80);
    await printHTML(token, '     <span class="muted">Power:</span>   n=24 per group · α=0.05 · 1-β=0.80 · <span class="key">d</span>=<span class="num">0.60</span>', 200);

    await printHTML(token, '&nbsp;', 100);

    // H2
    await printHTML(token, '<span class="paper-title">[H2]</span> <span class="key">novelty</span> <span class="num">0.71</span>  <span class="key">testability</span> <span class="num">0.86</span>', 140);
    await printHTML(token, '     <span class="muted">Claim:</span> ensembling diffusion pose prediction with classical docking', 80);
    await printHTML(token, '            lifts oncology virtual-screening hit-rate by ≥<span class="num">10</span> pp over', 80);
    await printHTML(token, '            either method alone.', 80);
    await printHTML(token, '     <span class="muted">Support:</span> <span class="doi">[4]</span> Sarvepalli &amp; Vadarevu 2025', 80);
    await printHTML(token, '     <span class="muted">Design:</span>  3 kinase panels · 10k-compound library · retrospective', 160);

    await printHTML(token, '&nbsp;', 100);
    await printHTML(token, '<span class="muted">+ 3 more (H3–H5) · ranked by combined score</span>', 160);
    await printHTML(token, '&nbsp;', 100);
    await printHTML(token, '<span class="sep-line">─────────────────────────────────────────────────────</span>', 200);
    await printHTML(token, '<span class="success">✓ Saved to</span> <span class="muted">projects/sci-hypothesis/2026-04-18_diffusion-kinase-gpcr.md</span>', 300);
    await printHTML(token, '<span class="muted">↳ proceed with H1? → protocol draft + power curve</span>', 200);
  }

  async function runAnalysis(token) {
    await typeLine(token, {
      prompt: '>',
      text: 'load kinase_results.csv and test group differences',
      speed: 44,
      pauseAfter: 600,
    });
    await routeHeader(token, {
      skill: 'sci-data-analysis',
      trigger: 'test group differences',
      reason: 'two-group comparison on continuous outcome',
    });

    await printHTML(token, '<span class="tool">→</span> <span class="muted">loaded kinase_results.csv · n=</span><span class="num">48</span> <span class="muted">· cols: group, rmsd_A, runtime_ms</span>', 180);
    await printHTML(token, '  <span class="key">diffusion:</span>   <span class="muted">n=</span><span class="num">24</span> <span class="muted">· mean=</span><span class="num">1.38</span> <span class="muted">Å · sd=</span><span class="num">0.41</span>', 100);
    await printHTML(token, '  <span class="key">equilibrium:</span> <span class="muted">n=</span><span class="num">24</span> <span class="muted">· mean=</span><span class="num">1.72</span> <span class="muted">Å · sd=</span><span class="num">0.38</span>', 260);

    await printHTML(token, '&nbsp;', 60);
    await printHTML(token, '<span class="tool">→</span> <span class="muted">assumption checks</span>', 200);
    await printHTML(token, '  <span class="muted">shapiro-wilk(diffusion)    </span><span class="key">W</span>=<span class="num">0.961</span>  <span class="key">p</span>=<span class="num">0.47</span>   <span class="success">✓</span> <span class="muted">normal</span>', 140);
    await printHTML(token, '  <span class="muted">shapiro-wilk(equilibrium)  </span><span class="key">W</span>=<span class="num">0.952</span>  <span class="key">p</span>=<span class="num">0.31</span>   <span class="success">✓</span> <span class="muted">normal</span>', 140);
    await printHTML(token, '  <span class="muted">levene(rmsd ~ group)       </span><span class="key">F</span>=<span class="num">0.082</span> <span class="key">p</span>=<span class="num">0.78</span>   <span class="success">✓</span> <span class="muted">equal variance</span>', 260);

    await printHTML(token, '&nbsp;', 80);
    await printHTML(token, '<span class="tool">→</span> <span class="muted">welch two-sample t-test (rmsd_A ~ group)</span>', 280);
    await printHTML(token, '  <span class="key">t</span>=<span class="num">2.98</span>  <span class="key">df</span>=<span class="num">45.8</span>  <span class="key">p</span>=<span class="num">0.0045</span>', 120);
    await printHTML(token, '  <span class="muted">mean diff = </span><span class="num">-0.34</span> <span class="muted">Å · 95% CI [</span><span class="num">-0.57</span><span class="muted">, </span><span class="num">-0.11</span><span class="muted">]</span>', 120);
    await printHTML(token, "  <span class=\"muted\">Cohen's </span><span class=\"key\">d</span>=<span class=\"num\">0.86</span>  <span class=\"muted\">(</span><span class=\"warn\">large effect</span><span class=\"muted\">)</span>", 320);

    await printHTML(token, '&nbsp;', 80);
    await printHTML(token, '<span class="success">✓</span> <span class="muted">plot saved:</span> <span class="doi">figures/kinase_rmsd_violin.png</span>', 240);
    await printHTML(token, '<span class="success">✓</span> <span class="muted">copied to ~/Downloads · opened in editor</span>', 200);
    await printHTML(token, '<span class="muted">↳ assumptions met — reporting guidance logged to context/learnings.md</span>', 200);
  }

  async function runWriting(token) {
    await typeLine(token, {
      prompt: '>',
      text: 'draft a 2-paragraph Results section from this analysis',
      speed: 44,
      pauseAfter: 600,
    });
    await routeHeader(token, {
      skill: 'sci-writing',
      trigger: 'draft … Results section',
      reason: 'manuscript drafting — 4-agent cascade',
    });

    await printHTML(token, '<span class="agent">→ sci-researcher</span><span class="muted"> : building evidence table…</span>', 120);
    const s1 = await spinner(token, 'querying CrossRef + Paperclip for anchor quotes', 1400);
    s1.innerHTML = '<span class="success">  ✓</span>  <span class="muted">8 evidence rows · 6 anchor quotes · .bib with 12 refs</span>';
    await sleep(300, token);

    await printHTML(token, '&nbsp;', 60);
    await printHTML(token, '<span class="agent">→ sci-writer</span><span class="muted">     : drafting Results with [@Key] markers…</span>', 120);
    const s2 = await spinner(token, 'writing paragraph 1 of 2', 1400);
    s2.innerHTML = '<span class="success">  ✓</span>  <span class="muted">204 words · every claim carries a citation marker</span>';
    await sleep(300, token);

    await printHTML(token, '&nbsp;', 60);
    await printHTML(token, '<span class="agent">→ sci-verifier</span><span class="muted">   : mechanical checks…</span>', 120);
    await printHTML(token, '    <span class="success">✓</span> <span class="muted">citation marker syntax valid</span>', 90);
    await printHTML(token, '    <span class="success">✓</span> <span class="muted">all DOIs resolve on CrossRef</span>', 90);
    await printHTML(token, '    <span class="success">✓</span> <span class="muted">hedging preserved — no "suggests" → "proves" drift</span>', 90);
    await printHTML(token, '    <span class="success">✓</span> <span class="muted">stats reporting complete (t, df, p, CI, d)</span>', 220);

    await printHTML(token, '&nbsp;', 60);
    await printHTML(token, '<span class="agent">→ sci-reviewer</span><span class="muted">   : adversarial pass (reads draft cold)…</span>', 120);
    const s3 = await spinner(token, 'running 5-phase review: FATAL / MAJOR / MINOR', 1400);
    s3.innerHTML = '<span class="warn">  ⚠</span>  <span class="muted">1× MINOR: replace "significantly" with effect size (Cohen\'s d)</span>';
    await sleep(260, token);
    await printHTML(token, '     <span class="success">✓</span> <span class="muted">no FATAL · no MAJOR · 1 MINOR (auto-fixable)</span>', 240);

    await printHTML(token, '&nbsp;', 80);
    await printHTML(token, '<span class="sep-line">─────────────────────────────────────────────────────</span>', 220);
    await printHTML(token, '<span class="success">✓ Saved:</span> <span class="muted">projects/sci-writing/kinase-conf/kinase-conf-draft.md</span>', 200);
    await printHTML(token, '<span class="success">✓</span> <span class="muted">bibliography: kinase-conf.bib (12 refs · CrossRef-verified)</span>', 200);
    await printHTML(token, '<span class="muted">↳ ready for figure insertion · run humanizer before submission? (y/n)</span>', 200);
  }

  async function runFigure(token) {
    await typeLine(token, {
      prompt: '>',
      text: 'generate a scientific illustration of the diffusion sampling process',
      speed: 44,
      pauseAfter: 600,
    });
    await routeHeader(token, {
      skill: 'viz-nano-banana',
      trigger: 'scientific illustration',
      reason: 'methods figure — conceptual schematic',
    });

    await printHTML(token, '<span class="tool">→</span> <span class="muted">style options:</span>', 220);
    await printHTML(token, '  <span class="key">[1]</span> <span class="paper-title">scientific</span>   <span class="muted">publication-quality, clean lines</span>   <span class="success">← default</span>', 90);
    await printHTML(token, '  <span class="key">[2]</span> <span class="paper-title">notebook</span>     <span class="muted">hand-drawn sketchnote</span>', 90);
    await printHTML(token, '  <span class="key">[3]</span> <span class="paper-title">color</span>        <span class="muted">warm editorial / outreach</span>', 90);
    await printHTML(token, '  <span class="key">[4]</span> <span class="paper-title">mono</span>         <span class="muted">black &amp; white, technical</span>', 300);

    await printHTML(token, '&nbsp;', 80);
    await typeLine(token, { prompt: '>', text: '1', speed: 90, pauseAfter: 450 });

    await printHTML(token, '&nbsp;', 80);
    await printHTML(token, '<span class="tool">→</span> <span class="muted">expanding prompt from research-profile.md…</span>', 180);
    await printHTML(token, '  <span class="muted">"clean schematic · ligand-pocket binding · diffusion steps</span>', 80);
    await printHTML(token, '  <span class="muted">   labeled x_T → x_0 · journal-figure aesthetic · white background"</span>', 260);

    await printHTML(token, '&nbsp;', 60);
    const s1 = await spinner(token, 'Gemini 3 Pro Image · generating 1536×1024', 2400);
    s1.innerHTML = '<span class="success">  ✓</span>  <span class="muted">rendered in 6.2s · 1536×1024 · PNG</span>';
    await sleep(300, token);

    await printHTML(token, '&nbsp;', 80);
    await printHTML(token, '<span class="success">✓ Saved:</span> <span class="doi">figures/diffusion-sampling-schematic.png</span>', 200);
    await printHTML(token, '<span class="success">✓</span> <span class="muted">copied to ~/Downloads · opened in editor</span>', 200);
    await printHTML(token, '<span class="sep-line">─────────────────────────────────────────────────────</span>', 240);
    await printHTML(token, '<span class="muted">↳ insert as Figure 1 of the manuscript? · push to Drive? (y/n)</span>', 200);
  }

  async function runPublish(token) {
    await typeLine(token, {
      prompt: '>',
      text: 'push the explainer draft to Substack',
      speed: 44,
      pauseAfter: 600,
    });
    await routeHeader(token, {
      skill: 'tool-substack',
      trigger: 'push … to Substack',
      reason: 'draft publish — markdown → ProseMirror',
    });

    await printHTML(token, '<span class="tool">→</span> <span class="muted">humanizer pass (deep · research-profile voice)…</span>', 140);
    await printHTML(token, '  <span class="success">✓</span> <span class="muted">AI-tell score: </span><span class="num">78</span> <span class="muted">→ </span><span class="num">94</span> <span class="muted">(+16) · em dashes: 7 → 1</span>', 260);

    await printHTML(token, '&nbsp;', 60);
    await printHTML(token, '<span class="tool">→</span> <span class="muted">converting markdown → Substack ProseMirror schema</span>', 160);
    await printHTML(token, '  <span class="success">✓</span> <span class="muted">1,842 words · 3 headings · 2 mermaid diagrams</span>', 160);

    await printHTML(token, '&nbsp;', 60);
    await printHTML(token, '<span class="tool">→</span> <span class="muted">pre-rendering mermaid (v10 label-linter pass)…</span>', 140);
    await printHTML(token, '  <span class="success">✓</span> <span class="muted">diagrams rendered to PNG · 2 files</span>', 200);

    await printHTML(token, '&nbsp;', 60);
    await printHTML(token, '<span class="tool">→</span> <span class="muted">uploading images to Substack CDN (3 files)</span>', 140);
    const s1 = await spinner(token, 'POST substackcdn.com/image/fetch', 1500);
    s1.innerHTML = '<span class="success">  ✓</span>  <span class="muted">3/3 uploaded · stable URLs returned</span>';
    await sleep(260, token);

    await printHTML(token, '&nbsp;', 60);
    await printHTML(token, '<span class="tool">→</span> <span class="muted">POST /api/v1/drafts</span>', 160);
    const s2 = await spinner(token, 'creating draft', 1200);
    s2.innerHTML = '<span class="success">  ✓</span>  <span class="success">201 Created</span><span class="muted"> · draft saved</span>';
    await sleep(300, token);

    await printHTML(token, '&nbsp;', 80);
    await printHTML(token, '<span class="sep-line">─────────────────────────────────────────────────────</span>', 200);
    await printHTML(token, '<span class="success">✓ Draft created:</span> <span class="paper-title">"Diffusion models are not a shortcut for drug design"</span>', 200);
    await printHTML(token, '  <span class="url">https://yourname.substack.com/publish/post/147839201</span>', 260);
    await printHTML(token, '<span class="muted">↳ opens in browser — review · publish is always a human click</span>', 200);
  }

  const SCRIPTS = {
    literature: runLiterature,
    hypothesis: runHypothesis,
    analysis:   runAnalysis,
    writing:    runWriting,
    figure:     runFigure,
    publish:    runPublish,
  };

  const TITLES = {
    literature: 'claude · organon — literature',
    hypothesis: 'claude · organon — hypothesis',
    analysis:   'claude · organon — analysis',
    writing:    'claude · organon — writing',
    figure:     'claude · organon — figure',
    publish:    'claude · organon — publish',
  };

  const SEQUENCE = ['literature', 'hypothesis', 'analysis', 'writing', 'figure', 'publish'];
  const ADVANCE_PAUSE_MS = 1200;

  function setActiveTab(scriptKey) {
    tabs.forEach((t) => {
      const active = t.dataset.script === scriptKey;
      t.classList.toggle('active', active);
      t.setAttribute('aria-selected', active ? 'true' : 'false');
    });
  }

  async function play(scriptKey) {
    currentScript = scriptKey;
    const token = newRun();
    clearBody();
    if (replayBtn) replayBtn.classList.remove('show');
    setActiveTab(scriptKey);
    if (termTitle) termTitle.textContent = TITLES[scriptKey] || 'claude · organon';
    try {
      await sleep(250, token);
      await SCRIPTS[scriptKey](token);
      if (token.aborted) return;
      if (replayBtn) replayBtn.classList.add('show');
      // Auto-advance to the next stage (loops back to literature after publish)
      await sleep(ADVANCE_PAUSE_MS, token);
      const idx = SEQUENCE.indexOf(scriptKey);
      const nextKey = SEQUENCE[(idx + 1) % SEQUENCE.length];
      play(nextKey);
    } catch (err) {
      if (err !== ABORTED) throw err;
    }
  }

  // Tab wiring — clicking a tab interrupts the auto-advance and restarts from that tab
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => play(tab.dataset.script));
  });

  if (replayBtn) {
    replayBtn.addEventListener('click', () => play(currentScript));
  }

  // Auto-start on first view
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            play('literature');
            io.disconnect();
          }
        });
      },
      { threshold: 0.2 }
    );
    io.observe(body);
  } else {
    play('literature');
  }

  // Copy buttons
  document.querySelectorAll('.copy-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const target = document.getElementById(btn.dataset.target);
      if (!target) return;
      try {
        await navigator.clipboard.writeText(target.textContent);
        const orig = btn.textContent;
        btn.textContent = 'Copied';
        btn.classList.add('copied');
        setTimeout(() => {
          btn.textContent = orig;
          btn.classList.remove('copied');
        }, 1400);
      } catch (err) {
        console.error('Copy failed:', err);
      }
    });
  });
})();
