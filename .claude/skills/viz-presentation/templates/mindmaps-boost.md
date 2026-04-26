---
marp: true
theme: default
paginate: true
math: katex
style: |
  @import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@400;500;700;800;900&family=Inter:wght@300;400;500&display=swap');

  /* =========================================================================
     Mindmaps Boost — warm editorial template
     Layout archetypes (use via <!-- _class: NAME -->):
       lead       — title slide: huge headline bottom-left, italic label top-right
       content    — default body slide (auto-applied): heading top-left, bullets
       stats      — 3-up numbers with color-pop values
       quote      — pull quote centered with left border
       figure     — image-dominant with caption
       closing    — end slide: large gratitude headline bottom-left
     Decorative blobs use ::before + ::after pseudo-elements. Stay in-slide via
     overflow:hidden. Tuned to match the SlidesGo Boost aesthetic.
     ========================================================================= */

  /* Base slide: off-white paper background, editorial typography */
  section {
    background: #faf5ef;
    color: #1a1a1a;
    font-family: 'Inter', -apple-system, sans-serif;
    font-size: 24px;
    padding: 55px 75px 60px 75px;
    position: relative;
    overflow: hidden;
  }

  /* Typography */
  h1, h2, h3 {
    font-family: 'Bricolage Grotesque', 'Inter', sans-serif;
    color: #1a1a1a;
    margin-top: 0;
    letter-spacing: -0.02em;
  }
  h1 { font-size: 52px; font-weight: 900; line-height: 1.0; }
  h2 { font-size: 38px; font-weight: 800; line-height: 1.05; }
  h3 { font-size: 24px; font-weight: 700; color: #a82a2a; text-transform: uppercase; letter-spacing: 0.08em; }
  strong { color: #a82a2a; font-weight: 700; }
  em { color: #6b4f4a; font-style: italic; }
  p, ul, ol { font-weight: 400; line-height: 1.5; }
  ul { padding-left: 24px; }
  li { margin-bottom: 10px; }

  /* Decorative blobs — soft coral shapes, positioned via radial gradients */
  section::before {
    content: '';
    position: absolute;
    width: 620px; height: 620px;
    top: -180px; right: -220px;
    background: radial-gradient(circle at center, #e89a8c 0%, #f2c4b5 40%, transparent 70%);
    border-radius: 50%;
    z-index: 0;
    pointer-events: none;
    opacity: 0.9;
  }
  section::after {
    content: '';
    position: absolute;
    width: 380px; height: 380px;
    bottom: -120px; left: -140px;
    background: radial-gradient(circle at center, #f5d9a8 0%, #f5e3c4 35%, transparent 70%);
    border-radius: 50%;
    z-index: 0;
    pointer-events: none;
    opacity: 0.85;
  }
  section > * { position: relative; z-index: 1; }

  /* Page number — reposition custom */
  section::after {
    /* keep decorative; page number handled by 'paginate' + footer */
  }

  /* =========================================================================
     Lead (title) slide
     ========================================================================= */
  section.lead {
    padding: 0;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    background: #faf5ef;
  }
  section.lead::before {
    width: 900px; height: 900px;
    top: -250px; right: -300px;
    background: radial-gradient(circle at center, #e89a8c 0%, #f2c4b5 35%, #faebd7 65%, transparent 80%);
    opacity: 1;
  }
  section.lead::after {
    width: 520px; height: 520px;
    bottom: -200px; left: -180px;
    background: radial-gradient(circle at center, #f5d9a8 0%, #f5e3c4 40%, transparent 75%);
    opacity: 0.9;
  }
  section.lead h1 {
    font-size: 120px;
    font-weight: 900;
    line-height: 0.92;
    padding: 0 80px 60px 80px;
    max-width: 1050px;
    letter-spacing: -0.035em;
  }
  section.lead h2 {
    font-family: 'Inter', sans-serif;
    font-size: 20px;
    font-weight: 400;
    font-style: italic;
    color: #4a3a36;
    position: absolute;
    top: 70px;
    right: 80px;
    text-align: right;
    max-width: 320px;
    letter-spacing: 0.01em;
    z-index: 2;
  }
  /* Author line on lead — use blockquote markdown: >  */
  section.lead blockquote {
    font-family: 'Inter', sans-serif;
    font-size: 18px;
    color: #6b4f4a;
    padding: 0 80px 40px 80px;
    border: none;
    font-style: normal;
  }

  /* =========================================================================
     Stats — 3-up grid with big coral numbers
     ========================================================================= */
  section.stats h2 { margin-bottom: 40px; }
  section.stats .stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 40px;
    margin-top: 30px;
  }
  section.stats .stat-num {
    font-family: 'Bricolage Grotesque', sans-serif;
    font-size: 88px;
    font-weight: 900;
    color: #a82a2a;
    line-height: 1;
    letter-spacing: -0.04em;
  }
  section.stats .stat-label {
    font-size: 16px;
    color: #4a3a36;
    margin-top: 8px;
    line-height: 1.3;
  }

  /* =========================================================================
     Quote — centered pull quote with left border
     ========================================================================= */
  section.quote {
    display: flex;
    align-items: center;
    justify-content: center;
  }
  section.quote blockquote {
    border-left: 6px solid #a82a2a;
    padding: 20px 40px;
    font-family: 'Bricolage Grotesque', sans-serif;
    font-size: 44px;
    font-weight: 500;
    line-height: 1.2;
    max-width: 900px;
    color: #1a1a1a;
    font-style: normal;
  }
  section.quote blockquote p:last-child {
    font-family: 'Inter', sans-serif;
    font-size: 18px;
    font-weight: 400;
    color: #6b4f4a;
    font-style: italic;
    margin-top: 24px;
  }

  /* =========================================================================
     Figure — image-dominant
     ========================================================================= */
  section.figure {
    padding: 50px 75px;
  }
  section.figure h2 { margin-bottom: 20px; }

  /* =========================================================================
     Closing
     ========================================================================= */
  section.closing {
    padding: 0;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
  }
  section.closing h1 {
    font-size: 108px;
    font-weight: 900;
    padding: 0 80px 60px 80px;
    line-height: 0.95;
    letter-spacing: -0.03em;
  }
  section.closing h2 {
    font-family: 'Inter', sans-serif;
    font-size: 18px;
    font-weight: 400;
    font-style: italic;
    color: #6b4f4a;
    position: absolute;
    top: 70px;
    right: 80px;
    text-align: right;
  }

  /* Tables, images, code unchanged from before */
  table { border-collapse: collapse; margin: 0 auto; background: rgba(255,255,255,0.6); backdrop-filter: blur(4px); border-radius: 8px; overflow: hidden; }
  th { background: #a82a2a; color: #faf5ef; padding: 12px 20px; font-weight: 700; text-align: left; }
  td { padding: 10px 20px; border-bottom: 1px solid rgba(168,42,42,0.15); }
  tr:last-child td { color: #a82a2a; font-weight: 700; }
  code { background: rgba(255,255,255,0.6); padding: 2px 6px; border-radius: 3px; }
  img[alt~="center"] { display: block; margin: 0 auto; border-radius: 8px; box-shadow: 0 4px 24px rgba(168,42,42,0.15); }
  section img { max-height: 380px; max-width: 100%; object-fit: contain; }
  footer { color: #6b4f4a; font-size: 12px; font-style: italic; z-index: 2; }
---
