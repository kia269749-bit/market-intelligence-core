import json
from pathlib import Path

def build_html(report,path):
    payload=json.dumps(report,ensure_ascii=False)
    html="<html><head><meta charset='utf-8'><title>Market Intelligence</title></head><body>"
    html+="<h1>Market Intelligence Core</h1><pre id='report'></pre>"
    html+="<script>const data="+payload+";document.getElementById('report').textContent=JSON.stringify(data,null,2);</script>"
    html+="</body></html>"
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(html,encoding="utf-8")
    return str(p)
