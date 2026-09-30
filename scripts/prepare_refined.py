"""Prepare the separately pinned catalog fixes, offline images and raw-data cache."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from weather_bench.refined import CATALOG,source_cache,verify_profile,build
from weather_bench.catalog import DEFAULT_CATALOG
pin=json.loads((ROOT/'catalog.refined.lock.json').read_text())
if not CATALOG.exists():
    subprocess.run(['git','-C',str(DEFAULT_CATALOG),'worktree','add','--detach',str(CATALOG),pin['catalog_commit']],check=True)
    subprocess.run(['git','-C',str(CATALOG),'apply',str(ROOT/'patches/catalog-reliability-v3.patch')],check=True)
verify_profile();root,metadata=source_cache();print(json.dumps(metadata),flush=True)
build()
subprocess.run([sys.executable,str(ROOT/'scripts/validate_refined.py')],check=True)

subprocess.run([sys.executable,str(ROOT/'scripts/validate_rolling_followup.py')],check=True)
subprocess.run([sys.executable,str(ROOT/'scripts/validate_refined.py'),'--overlay'],check=True)
