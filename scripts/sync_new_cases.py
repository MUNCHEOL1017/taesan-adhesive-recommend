"""새로 도착한 Eden Lee(헨켈) 메일을 IMAP으로 확인해서, 아직 검토 안 한 메일을
로컬 staged_emails.json에 원문 그대로 쌓아둔다. (AI 판단은 하지 않음 - 비용 없음)

이 스크립트는 Windows 작업 스케줄러 등으로 주기적으로 실행해두면 되고,
실제 "이게 케이스인지, 지식베이스에 어떻게 넣을지" 판단은 Claude Code 세션에서
사용자가 "새 메일 확인해줘"라고 요청할 때 이 파일을 읽어서 처리한다.
"""
import email as email_module
import imaplib
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from imap_extract import load_env, decode_mime, get_body_text  # noqa: E402

ENV_PATH = SCRIPT_DIR.parent / ".env"
STATE_PATH = SCRIPT_DIR / "data" / "sync_state.json"
STAGED_PATH = SCRIPT_DIR / "data" / "staged_emails.json"
TARGET_FOLDER = '"&1ejPCA-_Eden &x3TArLLY-"'

imaplib.Commands['ID'] = ('NONAUTH', 'AUTH', 'SELECTED', 'LOGOUT')


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"last_uid": 0}


def save_state(state: dict):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_staged() -> list:
    if STAGED_PATH.exists():
        return json.loads(STAGED_PATH.read_text(encoding="utf-8"))
    return []


def save_staged(items: list):
    STAGED_PATH.parent.mkdir(parents=True, exist_ok=True)
    STAGED_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    env = load_env(ENV_PATH)
    state = load_state()
    last_uid = int(state.get("last_uid", 0))

    conn = imaplib.IMAP4_SSL(env.get("NAVER_IMAP_HOST", "imap.naver.com"), int(env.get("NAVER_IMAP_PORT", "993")))
    conn._simple_command('ID', '("name" "AdhesiveKnowledgeBot" "version" "1.0" "vendor" "personal-script")')
    conn.login(env["NAVER_MAIL_ID"], env["NAVER_MAIL_APP_PASSWORD"])
    conn.select(TARGET_FOLDER, readonly=True)

    status, data = conn.uid('search', None, 'HEADER', 'FROM', '"Eden Lee"')
    all_uids = [int(u) for u in data[0].split()] if data and data[0] else []
    new_uids = sorted(u for u in all_uids if u > last_uid)

    print(f"이전 처리 기준 UID: {last_uid} | 전체 매칭 메일: {len(all_uids)}건 | 신규: {len(new_uids)}건")

    if not new_uids:
        conn.logout()
        print("신규 메일 없음.")
        return

    staged = load_staged()
    added, failed = 0, 0

    for uid in new_uids:
        try:
            status, msg_data = conn.uid('fetch', str(uid), '(RFC822)')
            if status != 'OK' or not msg_data or not msg_data[0]:
                failed += 1
                continue
            msg = email_module.message_from_bytes(msg_data[0][1])
            staged.append({
                "uid": uid,
                "subject": decode_mime(msg.get("Subject", "")),
                "date": msg.get("Date", ""),
                "body": get_body_text(msg),
            })
            added += 1
        except Exception as e:
            failed += 1
            print(f"  [UID {uid}] 처리 실패: {e}")

    conn.logout()
    save_staged(staged)
    save_state({"last_uid": max(new_uids)})

    print(f"\n완료: 신규 {added}건 저장(누적 대기 {len(staged)}건), 실패 {failed}건")
    if added:
        print(f"검토 대기 파일: {STAGED_PATH}")
        print('다음에 Claude Code에서 "새 메일 확인해줘"라고 요청하면 이 파일을 읽어 지식베이스 반영 여부를 판단합니다.')


if __name__ == "__main__":
    main()
