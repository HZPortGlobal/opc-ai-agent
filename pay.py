#!/usr/bin/env python3
"""
原生支付模块：微信支付 Native（扫码）+ 支付宝当面付（扫码）。
未配置商户参数时，相关函数抛 RuntimeError，由 app.py 走会员码兜底（manual_pending）。

环境变量（Render Environment）：
  微信：WECHAT_MCH_ID / WECHAT_APPID / WECHAT_SERIAL_NO /
        WECHAT_PRIVATE_KEY(商户私钥 PEM 内容或文件路径) / WECHAT_APIV3_KEY(32位) /
        WECHAT_PLATFORM_CERT_PEM(微信平台证书，验回调用，可暂缺) / WECHAT_NOTIFY_URL
  支付宝：ALIPAY_APP_ID / ALIPAY_APP_PRIVATE_KEY / ALIPAY_PUBLIC_KEY / ALIPAY_NOTIFY_URL
"""
import base64
import json
import os
import secrets
import time

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import store


def _load_key(pem_or_path):
    """支持直接传 PEM 字符串或文件路径。"""
    s = (pem_or_path or "").strip()
    if not s:
        raise RuntimeError("缺少私钥/证书配置")
    if "-----BEGIN" in s:
        return s
    with open(s, "r", encoding="utf-8") as f:
        return f.read()


def _rsa_sign_sha256(pem_or_path, message):
    key = serialization.load_pem_private_key(_load_key(pem_or_path).encode(), password=None)
    sig = key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()


def _rsa_verify_sha256(pub_pem, message, signature_b64):
    pub = serialization.load_pem_public_key(pub_pem.encode())
    pub.verify(base64.b64decode(signature_b64), message.encode("utf-8"),
               padding.PKCS1v15(), hashes.SHA256())


# ---------------- 微信支付（Native 扫码） ----------------

def wechat_native(order_no, amount_cny, description="AI 上架合规体检会员"):
    """统一下单 Native，返回 code_url（二维码内容）。"""
    mchid = os.environ.get("WECHAT_MCH_ID", "")
    appid = os.environ.get("WECHAT_APPID", "")
    serial_no = os.environ.get("WECHAT_SERIAL_NO", "")
    priv = os.environ.get("WECHAT_PRIVATE_KEY", "")
    notify = os.environ.get("WECHAT_NOTIFY_URL", "")
    if not (mchid and appid and serial_no and priv and notify):
        raise RuntimeError("微信支付商户配置不完整（MCH_ID/APPID/SERIAL/PRIVATE_KEY/NOTIFY_URL）")
    body = {
        "appid": appid,
        "mchid": mchid,
        "description": description,
        "out_trade_no": order_no,
        "notify_url": notify,
        "amount": {"total": int(round(amount_cny * 100)), "currency": "CNY"},
    }
    url_path = "/v3/pay/transactions/native"
    url = "https://api.mch.weixin.qq.com" + url_path
    ts = str(int(time.time()))
    nonce = secrets.token_hex(8)
    msg = f"POST\n{url_path}\n{ts}\n{nonce}\n{json.dumps(body, ensure_ascii=False)}\n"
    signature = _rsa_sign_sha256(priv, msg)
    auth = (
        f'WECHATPAY2-SHA256-RSA2048 mchid="{mchid}",nonce_str="{nonce}",'
        f'signature="{signature}",timestamp="{ts}",serial_no="{serial_no}"'
    )
    r = requests.post(url, json=body, timeout=15, headers={
        "Authorization": auth,
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    d = r.json()
    if r.status_code != 200 or "code_url" not in d:
        raise RuntimeError(f"微信下单失败({r.status_code}): {d}")
    return d["code_url"]


def wechat_verify_notify(headers, raw_body):
    """微信支付回调：验签（配了平台证书时）+ AES-GCM 解密 resource，返回订单对象。"""
    apiv3_key = os.environ.get("WECHAT_APIV3_KEY", "")
    if len(apiv3_key) != 32:
        raise RuntimeError("WECHAT_APIV3_KEY 需为 32 位")
    cert_pem = os.environ.get("WECHAT_PLATFORM_CERT_PEM", "")
    if cert_pem:
        _rsa_verify_sha256(
            _load_key(cert_pem),
            f'{headers.get("Wechatpay-Timestamp", "")}\n'
            f'{headers.get("Wechatpay-Nonce", "")}\n{raw_body}\n',
            headers.get("Wechatpay-Signature", ""),
        )
    res = json.loads(raw_body).get("resource", {})
    aesgcm = AESGCM(apiv3_key.encode())
    plain = aesgcm.decrypt(
        res.get("nonce", "").encode(),
        base64.b64decode(res.get("ciphertext", "")),
        res.get("associated_data", "").encode(),
    )
    return json.loads(plain)


# ---------------- 支付宝（当面付/扫码） ----------------

def _alipay_sign(params):
    priv = os.environ.get("ALIPAY_APP_PRIVATE_KEY", "")
    to_sign = "&".join(f"{k}={params[k]}" for k in sorted(params)
                       if params[k] and k not in ("sign", "sign_type"))
    return _rsa_sign_sha256(priv, to_sign)


def alipay_precreate(order_no, amount_cny, subject="AI 上架合规体检会员"):
    """当面付预下单，返回 qr_code（二维码内容）。"""
    app_id = os.environ.get("ALIPAY_APP_ID", "")
    notify = os.environ.get("ALIPAY_NOTIFY_URL", "")
    priv = os.environ.get("ALIPAY_APP_PRIVATE_KEY", "")
    if not (app_id and priv and notify):
        raise RuntimeError("支付宝商户配置不完整（APP_ID/PRIVATE_KEY/NOTIFY_URL）")
    biz = {"out_trade_no": order_no, "total_amount": f"{amount_cny:.2f}", "subject": subject}
    params = {
        "app_id": app_id,
        "method": "alipay.trade.precreate",
        "format": "JSON",
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "notify_url": notify,
        "biz_content": json.dumps(biz, ensure_ascii=False),
    }
    params["sign"] = _alipay_sign(params)
    r = requests.post("https://openapi.alipay.com/gateway.do", data=params, timeout=15)
    d = r.json()
    resp = d.get("alipay_trade_precreate_response", {})
    if resp.get("code") != "10000" or not resp.get("qr_code"):
        raise RuntimeError(f"支付宝下单失败: {resp}")
    return resp["qr_code"]


def alipay_verify_notify(form):
    """支付宝异步通知验签（RSA2）。"""
    pub = os.environ.get("ALIPAY_PUBLIC_KEY", "")
    if not pub:
        raise RuntimeError("缺少 ALIPAY_PUBLIC_KEY")
    sign = form.get("sign", "")
    to_verify = "&".join(f"{k}={form[k]}" for k in sorted(form)
                         if form[k] and k not in ("sign", "sign_type"))
    _rsa_verify_sha256(_load_key(pub), to_verify, sign)


# ---------------- 支付成功 → 自动发货 ----------------

def issue_member_code(channel, order_no, price_cny):
    """支付成功后 mint 会员码并写支付记录（自动发货，无需人工）。"""
    code = f"PAY-{secrets.token_hex(3).upper()}-{secrets.token_hex(3).upper()}"
    store.create_redeem_code(code, plan="pro", credits=9999)
    store.log_payment(channel, price_cny, "paid", code=code, meta=order_no)
    return code
