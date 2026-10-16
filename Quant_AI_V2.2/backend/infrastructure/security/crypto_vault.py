"""
Crypto Vault Module - Hardware-Bound Password Encryption
=========================================================
Mã hóa mật khẩu MT5 và các khóa bí mật bằng thuật toán AES-128 (Fernet)
kết hợp với Hardware UUID của bo mạch chủ/CPU máy tính Windows.
Bảo đảm không thể giải mã nếu tệp cấu hình bị sao chép sang máy tính khác.
"""

import base64
import hashlib
import platform
import uuid
from cryptography.fernet import Fernet

_SALT = b"QUANT_SYSTEM_V2_ENCRYPTION_SALT_SECURE_2026"
_PREFIX = "ENC:"


def _get_hardware_fingerprint() -> str:
    """
    Thu thập định danh phần cứng duy nhất của máy tính người dùng.
    """
    mac = str(uuid.getnode())
    node = platform.node()
    proc = platform.processor()
    system = platform.system()
    raw_id = f"{mac}:{node}:{proc}:{system}"
    return raw_id


def _get_fernet_cipher() -> Fernet:
    """
    Sinh khóa AES Fernet dựa trên Hardware Fingerprint qua hàm KDF chuẩn PBKDF2-SHA256.
    """
    fingerprint = _get_hardware_fingerprint()
    derived_32bytes = hashlib.pbkdf2_hmac(
        "sha256", fingerprint.encode("utf-8"), _SALT, iterations=100000
    )
    b64_key = base64.urlsafe_b64encode(derived_32bytes)
    return Fernet(b64_key)


def encrypt_secret(plaintext: str) -> str:
    """
    Mã hóa chuỗi bí mật (mật khẩu) ràng buộc với phần cứng máy tính.
    """
    if not plaintext:
        return ""
    if plaintext.startswith(_PREFIX):
        return plaintext  # Đã mã hóa từ trước

    cipher = _get_fernet_cipher()
    encrypted_bytes = cipher.encrypt(plaintext.encode("utf-8"))
    return _PREFIX + encrypted_bytes.decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """
    Giải mã chuỗi bí mật. Tự động hỗ trợ chuỗi cũ chưa mã hóa (Backward-compatible).
    """
    if not ciphertext:
        return ""
    if not ciphertext.startswith(_PREFIX):
        return ciphertext  # Chuỗi plaintext cũ, tự động trả về để nâng cấp

    token = ciphertext[len(_PREFIX) :].encode("utf-8")
    try:
        cipher = _get_fernet_cipher()
        decrypted_bytes = cipher.decrypt(token)
        return decrypted_bytes.decode("utf-8")
    except Exception as e:
        # Nếu copy sang máy tính khác, khóa không khớp sẽ ném lỗi InvalidToken
        return f"[LỖI GIẢI MÃ: Khóa phần cứng không khớp - {e}]"
