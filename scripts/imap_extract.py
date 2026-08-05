"""네이버메일 IMAP에서 'Eden' 폴더의 Eden Lee 발신 메일 전체를 다운로드해서
로컬 JSON 파일로 저장한다 (제목/날짜/발신자/본문 텍스트).
"""
import email
import imaplib
import json
import re
from email.header import decode_header
from email.utils import parseaddr
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
OUT_DIR = Path(__file__).resolve().parent / "data" / "raw_emails"
TARGET_FOLDER = '"&1ejPCA-_Eden &x3TArLLY-"'  # IMAP list()로 확인된 raw 폴더명

imaplib.Commands['ID'] = ('NONAUTH', 'AUTH', 'SELECTED', 'LOGOUT')


def load_env(path: Path) -> dict:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip()
    return values


def decode_mime(value: str) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            try:
                out.append(text.decode(enc or "utf-8", errors="replace"))
            except (LookupError, TypeError):
                out.append(text.decode("utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def strip_html(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def get_body_text(msg: email.message.Message) -> str:
    plain, html = None, None
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp:
                continue
            try:
                payload = part.get_payload(decode=True)
            except Exception:
                continue
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except (LookupError, TypeError):
                text = payload.decode("utf-8", errors="replace")
            if ctype == "text/plain" and plain is None:
                plain = text
            elif ctype == "text/html" and html is None:
                html = text
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace") if payload else ""
        if msg.get_content_type() == "text/html":
            html = text
        else:
            plain = text

    if plain and plain.strip():
        return plain.strip()
    if html:
        return strip_html(html)
    return ""


def main():
    env = load_env(ENV_PATH)
    host = env.get("NAVER_IMAP_HOST", "imap.naver.com")
    port = int(env.get("NAVER_IMAP_PORT", "993"))
    user = env["NAVER_MAIL_ID"]
    password = env["NAVER_MAIL_APP_PASSWORD"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = imaplib.IMAP4_SSL(host, port)
    conn._simple_command(
        'ID', '("name" "AdhesiveKnowledgeBot" "version" "1.0" "vendor" "personal-script")'
    )
    conn.login(user, password)
    conn.select(TARGET_FOLDER, readonly=True)

    status, data = conn.search(None, 'HEADER FROM "Eden Lee"')
    ids = data[0].split()
    print(f"총 {len(ids)}건 다운로드 시작")

    saved, failed = 0, 0
    for i, msg_id in enumerate(ids, 1):
        try:
            status, msg_data = conn.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                failed += 1
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            subject = decode_mime(msg.get("Subject", ""))
            date = msg.get("Date", "")
            from_name, from_addr = parseaddr(decode_mime(msg.get("From", "")))
            to_name, to_addr = parseaddr(decode_mime(msg.get("To", "")))
            body = get_body_text(msg)

            record = {
                "uid": msg_id.decode(),
                "subject": subject,
                "date": date,
                "from_name": from_name,
                "from_addr": from_addr,
                "to_addr": to_addr,
                "body": body,
            }

            safe_subject = re.sub(r'[\\/:*?"<>|]', "_", subject)[:60]
            fname = f"{i:04d}_{safe_subject}.json"
            (OUT_DIR / fname).write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            saved += 1
            if i % 20 == 0:
                print(f"  {i}/{len(ids)} 처리 중...")
        except Exception as e:
            failed += 1
            print(f"  [{i}] 실패: {e}")

    conn.logout()
    print(f"\n완료: 저장 {saved}건, 실패 {failed}건 -> {OUT_DIR}")


if __name__ == "__main__":
    main()
