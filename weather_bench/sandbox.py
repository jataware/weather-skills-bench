"""Networkless containers. Only fixtures and a fresh work directory are mounted.

Python never has catalog access, even in the skills arm. Skill invocations go
through the host broker to a separate container, making their trace observable.
"""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid
from .catalog import ROOT, DEFAULT_CATALOG, CORE_COMMIT, inventory, verify

ENABLED={"aggregate-temporal","clip-region","coarsen","concat","convert-calendar",
         "convert-to-totals","deaccumulate","difference","inspect-zarr","iod-mode-index",
         "provenance","rename","select","step-to-time","summarize-dim","unit-convert"}

DOCKERFILE='''FROM python:3.12-slim AS python
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
WORKDIR /work
CMD ["python", "-c", "import time; time.sleep(86400)"]
FROM python AS skills
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --no-deps "weather-skills-core @ git+https://github.com/rhiza-research/weather-skills-core@CORE_COMMIT"
COPY catalog /catalog
'''


def build_images(catalog=DEFAULT_CATALOG):
    verify(catalog)
    context=ROOT/".build"/"docker"
    if context.exists():
        shutil.rmtree(context)
    context.mkdir(parents=True)
    requirements=(ROOT/"requirements.lock").read_text().splitlines()
    (context/"requirements.txt").write_text("\n".join(x for x in requirements if not x.startswith("weather-skills-core"))+"\n")
    (context/"Dockerfile").write_text(DOCKERFILE.replace("CORE_COMMIT",CORE_COMMIT))
    for name,entry in inventory(catalog).items():
        if name in ENABLED:
            folder=Path(entry["doc"]).parent
            shutil.copytree(Path(catalog)/folder,context/"catalog"/folder,ignore=shutil.ignore_patterns("tests","__pycache__"))
    for target in ("python","skills"):
        subprocess.run(["docker","build","--target",target,"-t",f"weather-bench-{target}:v1",str(context)],check=True)


class Sandbox:
    def __init__(self,inputs,work,skills=False,catalog=DEFAULT_CATALOG,skills_only=False,runtime=None):
        runtime=runtime or {}
        self.enabled=runtime.get('enabled',ENABLED)
        self.inputs=Path(inputs).resolve(); self.work=Path(work).resolve()
        self.work.mkdir(parents=True,exist_ok=True)
        run_uid=os.getuid() or 65534
        run_gid=os.getgid() if os.getuid() else 65534
        if not os.getuid(): self.work.chmod(0o777)
        self.catalog=catalog; self.containers={}; self.image_ids={}; self.skills_only=skills_only
        from .execution_cache import ExecutionCache
        self.execution_cache=ExecutionCache(self.inputs,self.work) if runtime.get('memoize_skills') else None
        try:
            for kind in (["skills"] if skills_only else ["python","skills"] if skills else ["python"]):
                tag=f"weather-bench-{kind}:"+runtime.get('tag','v1')
                image_id=subprocess.check_output(["docker","image","inspect",tag,"--format","{{.Id}}"],text=True).strip()
                self.image_ids[kind]=image_id
                name="weather-bench-"+uuid.uuid4().hex
                command=["docker","run","--detach","--name",name,"--network",runtime.get('network','none'),"--read-only",
                         "--cap-drop=ALL","--security-opt","no-new-privileges","--pids-limit","128",
                         "--memory",runtime.get('memory','1g'),"--cpus","1","--user",f"{run_uid}:{run_gid}",
                         "--tmpfs","/tmp:rw,nosuid,size=128m",
                         "--mount",f"type=bind,src={self.inputs},dst=/inputs,readonly",
                         "--mount",f"type=bind,src={self.work},dst=/work"]
                for key,value in runtime.get('environment',{}).items():command += ['--env',key+'='+value]
                command.append(image_id)
                subprocess.run(command,check=True,capture_output=True,text=True,timeout=60)
                self.containers[kind]=name
        except BaseException:
            self.close(); raise

    def execute(self,action,timeout=45):
        started=time.monotonic(); kind=action["action"]
        if kind=="python":
            if self.skills_only:
                raise ValueError("Arbitrary code execution is disabled in skills-only")
            target="python"; command=["python","-c",action["code"]]
        elif kind=="skill":
            name=action["skill"]
            if name not in self.enabled or "skills" not in self.containers:
                raise ValueError("Skill unavailable in this arm")
            if not isinstance(action.get("args"),list) or not all(isinstance(x,str) for x in action["args"]):
                raise ValueError("args must be an array of strings")
            target="skills"
            command=["python","/catalog/"+inventory(self.catalog)[name]["scripts"][0],*action["args"]]
        else:
            raise ValueError("Expected python or skill")
        cache_key=self.execution_cache.key(action,self.image_ids[target]) if self.execution_cache and kind=='skill' else None
        cached=self.execution_cache.get(cache_key) if self.execution_cache else None
        if cached:
            return {**cached,'seconds':time.monotonic()-started}
        try:
            proc=subprocess.run(["docker","exec",self.containers[target],*command],capture_output=True,text=True,timeout=timeout)
            result={"returncode":proc.returncode,"stdout":proc.stdout[:16000],"stderr":proc.stderr[-8000:],
                    "seconds":time.monotonic()-started}
            if self.execution_cache:self.execution_cache.put(cache_key,result)
            return result
        except subprocess.TimeoutExpired:
            # Killing docker exec alone leaves the code running. Stop the container.
            subprocess.run(["docker","kill",self.containers[target]],capture_output=True,timeout=15)
            return {"returncode":124,"stdout":"","stderr":"Execution deadline exceeded; task container stopped", "seconds":time.monotonic()-started}

    def submit_artifacts(self,fields):
        from .artifacts import validate_manifest, SERIALIZE_CODE
        validate_manifest(fields)
        started=time.monotonic()
        target=self.containers.get("skills") or self.containers["python"]
        proc=subprocess.run(["docker","exec",target,"python","-c",SERIALIZE_CODE,json.dumps(fields)],
                            capture_output=True,text=True,timeout=45)
        return {"returncode":proc.returncode,"stdout":proc.stdout[:16000],"stderr":proc.stderr[-8000:],"seconds":time.monotonic()-started}

    def answer(self):
        # Read through the container, never follow agent-created host symlinks.
        code="from pathlib import Path; p=Path('/work/answer.json'); assert p.stat().st_size < 100000; print(p.read_text())"
        if getattr(self,"skills_only",False):
            proc=subprocess.run(["docker","exec",self.containers["skills"],"python","-c",code],capture_output=True,text=True,timeout=30)
            response={"returncode":proc.returncode,"stdout":proc.stdout}
        else:
            response=self.execute({"action":"python","code":code})
        if response["returncode"]:
            return None
        try:
            parsed=json.loads(response["stdout"])
            def finite(value):
                if isinstance(value,float): return math.isfinite(value)
                if isinstance(value,dict): return all(finite(v) for v in value.values())
                if isinstance(value,list): return all(finite(v) for v in value)
                return True
            return parsed if finite(parsed) else None
        except (ValueError,TypeError,RecursionError):
            return None

    def close(self):
        for name in self.containers.values():
            subprocess.run(["docker","rm","-f",name],capture_output=True,timeout=30)
        self.containers.clear()

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()
