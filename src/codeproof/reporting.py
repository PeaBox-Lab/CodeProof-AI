from pathlib import Path
from html import escape
def markdown(r):
    rows=["| Check | Status | Weight | Summary |","|---|---|---:|---|"]+[f"| {x.name} | {x.status.value} | {x.weight:g} | {x.summary} |" for x in r.results]
    return f"# CodeProof: {r.project}\n\n**Score:** {r.score}/100 ({r.grade})  \n**Policy:** {'PASS' if r.policy_passed else 'FAIL'}\n\n"+"\n".join(rows)+"\n\n## Limitations\n"+"\n".join('- '+x for x in r.limitations)
def html(r):
    rows=''.join(f'<tr><td>{escape(x.name)}</td><td>{x.status.value}</td><td>{x.weight:g}</td><td>{escape(x.summary)}</td></tr>' for x in r.results)
    return f'<!doctype html><meta charset="utf-8"><title>CodeProof</title><style>body{{font-family:system-ui;max-width:1000px;margin:40px auto}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:8px}}</style><h1>CodeProof: {escape(r.project)}</h1><h2>{r.score}/100 ({r.grade})</h2><p>Policy: {"PASS" if r.policy_passed else "FAIL"}</p><table><tr><th>Check</th><th>Status</th><th>Weight</th><th>Summary</th></tr>{rows}</table>'
def write(r,out:Path,fmt:str):
    out.mkdir(parents=True,exist_ok=True);made=[]
    if fmt in ("all","json"):p=out/"codeproof-report.json";p.write_text(r.model_dump_json(indent=2));made.append(p)
    if fmt in ("all","markdown"):p=out/"codeproof-report.md";p.write_text(markdown(r));made.append(p)
    if fmt in ("all","html"):p=out/"codeproof-report.html";p.write_text(html(r));made.append(p)
    raw=out.parent/"raw";raw.mkdir(parents=True,exist_ok=True)
    for x in r.results:
        if x.raw_output:(raw/f"{x.name}.txt").write_text(x.raw_output)
    return made
