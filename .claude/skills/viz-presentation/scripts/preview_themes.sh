#!/usr/bin/env bash
# Render every template in templates/ with the shared sample body,
# write a gallery index.html, and serve it on localhost.
#
# Usage:
#   preview_themes.sh [output_dir]
#
# Default output_dir is a tmp dir. Prints the gallery URL on stdout.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATES_DIR="$SKILL_DIR/templates"
SAMPLE_BODY="$TEMPLATES_DIR/_sample-body.md"
CATALOG="$TEMPLATES_DIR/catalog.json"

OUT_DIR="${1:-${TMPDIR:-/tmp}/viz-presentation-gallery}"
mkdir -p "$OUT_DIR"

if [[ ! -f "$SAMPLE_BODY" ]]; then
  echo "ERROR: sample body not found at $SAMPLE_BODY" >&2
  exit 1
fi

# Determine marp command
if command -v marp &>/dev/null; then
  MARP="marp"
elif command -v npx &>/dev/null; then
  MARP="npx @marp-team/marp-cli"
else
  echo "ERROR: marp-cli not found. Run scripts/setup.sh first." >&2
  exit 1
fi

# Render each template (skip files starting with _)
CARDS=""
for tpl in "$TEMPLATES_DIR"/*.md; do
  base="$(basename "$tpl" .md)"
  [[ "$base" == _* ]] && continue

  # Prefer template-specific sample body if present: {id}.sample.md
  # Lets each template showcase its own layout archetypes + decorative elements,
  # not just a color swap over the same 4 generic slides.
  specific_sample="$TEMPLATES_DIR/${base}.sample.md"
  body_to_use="$SAMPLE_BODY"
  [[ -f "$specific_sample" ]] && body_to_use="$specific_sample"

  combined="$OUT_DIR/${base}.md"
  cat "$tpl" "$body_to_use" > "$combined"

  # Render to HTML (ignore warnings, just check success)
  if $MARP --html --allow-local-files "$combined" -o "$OUT_DIR/${base}.html" 2>/dev/null; then
    # Fetch name+description from catalog if present
    if [[ -f "$CATALOG" ]] && command -v python3 &>/dev/null; then
      meta=$(python3 -c "
import json, sys
try:
    c = json.load(open('$CATALOG'))
    for t in c.get('templates', []):
        if t.get('id') == '$base':
            print(f\"{t.get('name','$base')}|||{t.get('description','')}|||{t.get('best_for','')}\")
            sys.exit(0)
except Exception:
    pass
print('$base|||Custom template|||')
")
      name="${meta%%|||*}"
      rest="${meta#*|||}"
      desc="${rest%%|||*}"
      best="${rest#*|||}"
    else
      name="$base"
      desc="Custom template"
      best=""
    fi

    CARDS+="  <div class=\"card\">
    <div class=\"card-header\"><h2>${name}</h2><span class=\"badge\">${base}</span></div>
    <a href=\"${base}.html\" target=\"_blank\"><iframe src=\"${base}.html\" loading=\"lazy\"></iframe></a>
    <div class=\"desc\"><strong>${desc}</strong><br><em>Best for:</em> ${best}</div>
    <div class=\"card-footer\">
      <a href=\"${base}.html\" target=\"_blank\">Open full</a>
      <span class=\"choose\">To pick: say \"use ${base}\"</span>
    </div>
  </div>
"
  fi
done

# Write gallery index
cat > "$OUT_DIR/index.html" <<HTMLEOF
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>viz-presentation — Template Gallery</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f5f7; color: #222; padding: 40px; }
  h1 { font-size: 32px; margin-bottom: 8px; }
  .subtitle { color: #666; margin-bottom: 32px; font-size: 16px; max-width: 720px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(480px, 1fr)); gap: 24px; }
  .card { background: #fff; border-radius: 12px; overflow: hidden;
          box-shadow: 0 2px 8px rgba(0,0,0,0.06); transition: transform 0.2s; }
  .card:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,0.1); }
  .card-header { padding: 16px 22px; border-bottom: 1px solid #eee; display: flex;
                 align-items: baseline; justify-content: space-between; }
  .card-header h2 { font-size: 20px; }
  .card-header .badge { font-size: 11px; color: #888; text-transform: uppercase;
                        letter-spacing: 0.05em; background: #f0f0f0; padding: 3px 8px; border-radius: 4px; }
  .card iframe { width: 100%; height: 420px; border: 0; display: block; background: #fff; }
  .card-footer { padding: 12px 22px; display: flex; gap: 12px; font-size: 13px;
                 border-top: 1px solid #eee; background: #fafafa; justify-content: space-between; }
  .card-footer a { color: #0066cc; text-decoration: none; font-weight: 500; }
  .card-footer a:hover { text-decoration: underline; }
  .card-footer .choose { color: #888; font-style: italic; }
  .desc { padding: 14px 22px; color: #555; font-size: 14px; line-height: 1.5; background: #fafafa; }
  .desc strong { color: #222; }
  .desc em { color: #888; }
</style>
</head>
<body>
<h1>viz-presentation — Template Gallery</h1>
<p class="subtitle">Same sample deck rendered in every available template. Pick one by telling me its id (e.g. <em>"use dark-academia"</em>), or keep going and I'll default to <em>default</em>.</p>
<div class="grid">
${CARDS}
</div>
</body>
</html>
HTMLEOF

# Start server
URL="$(bash "$SCRIPT_DIR/serve_preview.sh" "$OUT_DIR")"
echo "${URL}/index.html"
