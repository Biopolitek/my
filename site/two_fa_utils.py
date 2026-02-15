import hmac
import hashlib
import time
import base64
import struct

def get_hotp_token(secret, intervals_no):
    """Generates a HOTP value (Helper for TOTP)."""
    # Декодируем секрет из Base32
    key = base64.b32decode(secret, True)
    # Форматируем номер интервала в байты
    msg = struct.pack(">Q", intervals_no)
    # Вычисляем HMAC-SHA1
    h = hmac.new(key, msg, hashlib.sha1).digest()
    # Dynamic Truncation
    o = h[19] & 15
    h_int = struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff
    # Генерируем 6-значный код
    return h_int % 1000000

def get_totp_token(secret):
    """Generates a TOTP value based on current time (RFC 6238)."""
    interval = 30  # Стандартный интервал в секундах
    intervals_no = int(time.time() // interval)
    return get_hotp_token(secret, intervals_no)

def verify_totp(secret, user_input_code):
    """Verifies the user provided code against the generated one."""
    expected_code = get_totp_token(secret)
    # Проверяем также предыдущий интервал на случай рассинхрона
    expected_code_prev = get_hotp_token(secret, int(time.time() // 30) - 1)
    
    return str(user_input_code) == str(expected_code).zfill(6) or str(user_input_code) == str(expected_code_prev).zfill(6)