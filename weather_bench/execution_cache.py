"""Per-run memoization of successful, unchanged skill artifacts; no shared answers."""
import hashlib
import json
from pathlib import Path
from .catalog import tree_hash


class ExecutionCache:
    def __init__(self, inputs, work):
        self.inputs=Path(inputs).resolve();self.work=Path(work).resolve();self.entries={}

    def path(self, name):
        for prefix,root in (('/inputs/',self.inputs),('/work/',self.work)):
            if name.startswith(prefix):
                p=root/name[len(prefix):]
                if not p.is_symlink() and p.resolve().is_relative_to(root):return p
        return None

    def fingerprint(self, name):
        p=self.path(name)
        if p is None or not p.exists():return None
        if p.is_dir():
            if any(q.is_symlink() for q in p.rglob('*')):return None
            return tree_hash(p)
        return hashlib.sha256(p.read_bytes()).hexdigest()

    def key(self, action, image):
        args=action['args'];out=[]
        for i,arg in enumerate(args[:-1]):
            if arg in ('-o','--output'):out.append(args[i+1])
        if not out or any(not x.startswith('/work/') for x in out):return None
        sources=[x for x in args if x.startswith(('/work/','/inputs/')) and x not in out]
        # No cache for remote retrieval, inspection or in-place transformations.
        if not sources or any(args.count(x)>1 for x in out):return None
        hashes=[self.fingerprint(x) for x in sources]
        if any(x is None for x in hashes):return None
        key=json.dumps([image,action,hashes],sort_keys=True)
        return key,out

    def get(self, key):
        if key is None:return None
        token,out=key;entry=self.entries.get(token)
        if not entry or [self.fingerprint(x) for x in out]!=entry['outputs']:return None
        return {**entry['result'],'seconds':0.,'cache_hit':True,'cached_execution_seconds':entry['result']['seconds']}

    def put(self,key,result):
        if key is None or result['returncode']:return
        token,out=key;hashes=[self.fingerprint(x) for x in out]
        if all(x is not None for x in hashes):self.entries[token]={'outputs':hashes,'result':result}
