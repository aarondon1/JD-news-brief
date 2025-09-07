from jinja2 import Template
from datetime import datetime

HTML_TMPL = Template("""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Morning Brief</title>
  <style>
    body { font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin:0; padding:0; background:#0f1220; color:#e8eaf6; }
    .wrap { max-width: 700px; margin: 0 auto; padding: 24px; }
    .card { background:#161a2b; border-radius:16px; padding:20px; box-shadow: 0 2px 12px rgba(0,0,0,0.3); }
    h1 { margin: 0 0 12px 0; font-size: 20px; }
    .item { padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.08); }
    .item:last-child { border-bottom: none; }
    a { color:#9ac7ff; text-decoration: none; }
    .src { font-size: 12px; opacity: .8; }
    .footer { margin-top: 16px; font-size: 12px; opacity: .7; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Morning Brief — {{ date_str }}</h1>
      {% for it in items %}
        <div class="item">
          <div>{{ it.summary }}</div>
          <div class="src"><a href="{{ it.url }}">{{ it.source }}</a></div>
        </div>
      {% endfor %}
      <div class="footer">Generated automatically. Sources linked above.</div>
    </div>
  </div>
</body>
</html>
""")

def render_html(items):
    date_str = datetime.utcnow().strftime("%A, %B %d, %Y")
    return HTML_TMPL.render(items=items, date_str=date_str)

def render_text(items):
    lines = [f"Morning Brief — {datetime.utcnow().strftime('%A, %B %d, %Y')}", ""]
    for it in items:
        lines.append(f"- {it['summary']} ({it['source']})")
        lines.append(f"  {it['url']}")
    return "\n".join(lines)
