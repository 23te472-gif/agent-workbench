"""Read-only source/dependency preflight. No GUI, model, scan or state creation."""
from pathlib import Path
import ast,importlib.util,json,sys
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parent
errors=[]
files=list(root.rglob('*.py'))
files=[p for p in files if not any(x in {'.venv','node_modules','data','logs','__pycache__'} for x in p.relative_to(root).parts)]
for path in files:
 try:ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))
 except (SyntaxError,UnicodeError) as e:errors.append(str(e))
for name in ('webview','clr_loader','PIL','tkinter'):
 try:found=importlib.util.find_spec(name) is not None
 except (ValueError,ImportError):found=False
 print(('OK ' if found else 'MISSING ')+name)
 if not found:errors.append('Install dependency: '+name)
frontends=[root/'frontend'] if (root/'frontend').is_dir() else [root/'tools/个人工具中心新版/frontend',root/'tools/宝可梦小镇新版/frontend']
for folder in frontends:
 for rel in ('dist/index.html','dist/assets/app.js','dist/assets/app.css'):
  if not (folder/rel).is_file():errors.append('Missing build: '+str(folder.relative_to(root)/rel))
print(f'Parsed {len(files)} Python source files; {len(errors)} issue(s).')
for error in errors:print(error)
print('No GUI, external program, model request or user data was opened.')
sys.exit(bool(errors))
