"""生成一对 VAPID 密钥，打印成 .env 可直接粘贴的两行。

用法：
    cd backend && ./.venv/bin/python -m app.gen_vapid

把打印的 VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY 填进 .env（或 compose 的环境变量）。
公钥前端走 GET /api/push/public-key 拿；私钥只在服务端，别外泄。
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def generate() -> tuple[str, str]:
    """返回 (public_key_b64url, private_key_b64url)，均为 pywebpush / 浏览器可用格式。"""
    key = ec.generate_private_key(ec.SECP256R1())
    priv = key.private_numbers().private_value.to_bytes(32, "big")
    pub = key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )  # 65 字节：0x04 || X || Y，正是浏览器 applicationServerKey 要的
    return _b64url(pub), _b64url(priv)


def main() -> None:
    public, private = generate()
    print("VAPID_PUBLIC_KEY=" + public)
    print("VAPID_PRIVATE_KEY=" + private)


if __name__ == "__main__":
    main()
