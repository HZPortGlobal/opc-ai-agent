"""
通过 GitHub REST API 的 Contents API 把本地仓库文件推送到远程。
适用于：git 协议被墙，但 api.github.com 可达；也适用于纯空仓库（自动初始化）。
用法:
  python push_via_api.py --owner HZPortGlobal --repo opc-ai-agent --token ghp_xxx
token 也可用环境变量 GITHUB_TOKEN 传入。
"""
import os
import sys
import json
import base64
import subprocess
import urllib.request
import urllib.error

API = "https://api.github.com"


def repo_dir():
    return os.path.dirname(os.path.abspath(__file__))


def tracked_files():
    out = subprocess.check_output(["git", "ls-files"], cwd=repo_dir()).decode()
    return [l for l in out.splitlines() if l.strip()]


def call(method, path, data=None, auth=None):
    url = f"{API}{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=auth, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, (r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode() or "{}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    args = ap.parse_args()
    if not args.token:
        sys.exit("缺少 token：用 --token 或环境变量 GITHUB_TOKEN")
    token = args.token.strip()
    base = f"/repos/{args.owner}/{args.repo}"
    auth = {"Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "opc-push"}

    # 取默认分支（空仓库也会返回，如 main / master）
    st, js = call("GET", base, auth=auth)
    if st != 200:
        sys.exit(f"无法读取仓库信息: {st} {js}")
    branch = json.loads(js).get("default_branch", "main")
    print(f"目标分支: {branch}")

    files = tracked_files()
    print(f"待推送文件: {len(files)} 个")
    ok = 0
    for f in files:
        p = os.path.join(repo_dir(), f)
        with open(p, "rb") as fh:
            raw = fh.read()
        payload = {
            "message": f"update {f}",
            "content": base64.b64encode(raw).decode(),
            "branch": branch,
        }
        # 文件已存在时需要带 sha 才能更新；不存在(404)则创建
        gst, gjs = call("GET", f"{base}/contents/{f}", auth=auth)
        if gst == 200:
            sha = json.loads(gjs).get("sha")
            if sha:
                payload["sha"] = sha
        st, js = call("PUT", f"{base}/contents/{f}", payload, auth)
        if st in (200, 201):
            ok += 1
            print(f"  OK  {f}")
        else:
            print(f"  FAIL {f}: {st} {json.loads(js).get('message')}")
    print(f"\n完成 {ok}/{len(files)} -> https://github.com/{args.owner}/{args.repo}")


if __name__ == "__main__":
    main()
