import json, time, urllib.request, urllib.error

BASE = "https://ai-agent-8krn.onrender.com"

def req(method, url, body=None, timeout=60):
    r = urllib.request.Request(url, method=method)
    if body is not None:
        r.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    else:
        data = None
    try:
        with urllib.request.urlopen(r, data=data, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return -1, str(e).encode()

print("=== 等重部署（90s） ===")
time.sleep(90)
for i in range(6):
    st, body = req("POST", BASE + "/api/pay/create", {"channel": "alipay"})
    print(f"[{i+1}] HTTP {st}")
    try:
        d = json.loads(body)
        s = json.dumps(d, ensure_ascii=False)
        print(s[:500])
        if d.get("qr_code"):
            print()
            print("=== SUCCESS: 拿到支付宝付款二维码！ ===")
            break
        if d.get("message") and "Invalid Arguments" not in s:
            print("新错误类型，看内容")
    except Exception:
        print(body.decode("utf-8", "ignore")[:400])
    time.sleep(20)
