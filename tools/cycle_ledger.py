from pathlib import Path
import json,datetime,hashlib
BASE=Path(__file__).resolve().parents[1]
def record(number,problem,change,test,evidence):
    file=BASE/'evidence/optimization_cycles.json'
    rows=json.loads(file.read_text()) if file.exists() else []
    if number<=len(rows): return  # regression reruns do not invent extra optimisation cycles
    assert number==len(rows)+1
    rows.append(dict(cycle=number,time=datetime.datetime.now().astimezone().isoformat(),problem=problem,improvement=change,test=test,evidence=evidence,result='PASS',source_sha256={str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (BASE/'off').glob('*.py')}))
    file.write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
if __name__=='__main__':
    record(1,'Toolbar command frames made drafting workspace visually heavy; modes and modal operations still need visible state.','Compact outline drafting icons, transparent idle toolbar, subtle hover, persistent selected underline; preserve command/worker state.','Actual Qt pointer clicks, modal open/close, exclusive tools and asynchronous worker state.','button_feedback_validation.json')
