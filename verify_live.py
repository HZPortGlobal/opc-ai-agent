import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod

c = appmod.app.test_client()
r = c.post(
    "/api/check",
    json={
        "brief": "Men's 3/2mm wetsuit, best thermal protection, 100% safe, unbreakable zipper, color black, perfect for surfing",
        "market": "uk",
    },
)
d = r.get_json()
print("STATUS:", r.status_code)
print("KEYS:", list(d.keys()))
print("model_down:", d.get("model_down"))
print("cost_cny:", d.get("cost_cny"))
out = d.get("output", "")
print("OUTPUT_LEN:", len(out))
print("OUTPUT_HEAD:", out[:600])
