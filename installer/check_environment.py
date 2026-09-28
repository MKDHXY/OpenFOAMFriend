import sys,json
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from install_core import environment
result=environment();print(json.dumps(result,indent=2,ensure_ascii=False));sys.exit(0 if result['ready'] else 2)
