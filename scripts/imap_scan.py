"""네이버메일 IMAP 스캔 스크립트.
.env 의 자격 증명으로 접속해서 폴더 목록과, 조건에 맞는 메일 수/제목만 먼저 보여준다.
본문 다운로드는 하지 않는 1단계 확인용 스크립트.
"""
import imaplib
import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env(path: Path) -> dict:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip()
    return values


def decode_mutf7(name: bytes) -> str:
    # IMAP modified UTF-7 폴더명 디코딩 (표시용)
    try:
        return name.decode("utf-7").replace("&-", "&")
    except Exception:
        return name.decode(errors="replace")


def main():
    env = load_env(ENV_PATH)
    host = env.get("NAVER_IMAP_HOST", "imap.naver.com")
    port = int(env.get("NAVER_IMAP_PORT", "993"))
    user = env["NAVER_MAIL_ID"]
    password = env["NAVER_MAIL_APP_PASSWORD"]

    print(f"접속 중: {host}:{port} (id={user})")
    conn = imaplib.IMAP4_SSL(host, port)

    # 네이버 IMAP은 LOGIN 전에 ID 커맨드(RFC 2971)를 요구한다.
    # imaplib은 ID를 표준 커맨드로 인식하지 못하므로 상태표에 직접 등록한다.
    imaplib.Commands['ID'] = ('NONAUTH', 'AUTH', 'SELECTED', 'LOGOUT')
    try:
        typ, dat = conn._simple_command(
            'ID', '("name" "AdhesiveKnowledgeBot" "version" "1.0" "vendor" "personal-script")'
        )
        print(f"ID 커맨드 응답: {typ} {dat}")
    except Exception as e:
        print(f"ID 커맨드 전송 실패(무시하고 진행): {e}")

    conn.login(user, password)
    print("로그인 성공\n")

    status, mailboxes = conn.list()
    if status != "OK":
        print("폴더 목록 조회 실패:", mailboxes)
        return

    print("=== 폴더 목록 ===")
    folder_raw_names = []
    for raw in mailboxes:
        # 예: b'(\\HasNoChildren) "/" "INBOX"'
        line = raw.decode(errors="replace")
        parts = line.split(' "/" ')
        if len(parts) == 2:
            folder_name = parts[1].strip('"')
        else:
            folder_name = line
        folder_raw_names.append(folder_name)
        print(f"- {folder_name}  (표시명: {decode_mutf7(folder_name.encode())})")

    print("\n=== 'Eden Lee' 발신 + 접착제 관련 메일 스캔 ===")
    total = 0
    for folder in folder_raw_names:
        try:
            status, _ = conn.select(f'"{folder}"', readonly=True)
            if status != "OK":
                continue
        except Exception as e:
            print(f"[{folder}] 선택 실패: {e}")
            continue

        status, data = conn.search(None, 'HEADER FROM "Eden Lee"')
        if status != "OK" or not data or not data[0]:
            continue

        ids = data[0].split()
        if not ids:
            continue

        print(f"\n[{decode_mutf7(folder.encode())}] {len(ids)}건")
        total += len(ids)

        # 최근 5건만 제목 샘플로 확인
        for msg_id in ids[-5:]:
            status, msg_data = conn.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])")
            if status == "OK" and msg_data and msg_data[0]:
                header = msg_data[0][1].decode(errors="replace")
                print(f"  · {header.strip()}")

    print(f"\n총 매칭 메일 수: {total}건")
    conn.logout()


if __name__ == "__main__":
    main()
