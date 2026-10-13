"""헨켈 메일 동기화 상태 점검 (Windows 작업 스케줄러에서 주 2회 실행).

AI 호출 없이 로컬 상태만 확인하고, 결과를 scripts/data/health_report.txt 에 남기며
Windows 알림(풍선 팁)으로 요약을 띄운다. 새 메일 판단/지식베이스 반영은 하지 않는다 -
"미검토 메일 N건"이 보이면 Claude Code에서 "새 메일 확인해줘"라고 요청하면 된다.
"""
import base64
import json
import subprocess
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
TASK_NAME = "헨켈메일동기화"
SITE_JSON = "https://muncheol1017.github.io/taesan-adhesive-recommend/case_studies.json"
MAX_SILENCE = timedelta(hours=48)  # 하루 2회 실행이므로 48시간 넘게 조용하면 이상


def powershell(script: str, timeout: int = 60) -> str:
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    result = subprocess.run(
        ["powershell", "-NoProfile", "-EncodedCommand", encoded],
        capture_output=True, timeout=timeout,
    )
    return result.stdout.decode("utf-8", errors="replace").strip()


def task_info() -> dict:
    script = (
        f"$i = Get-ScheduledTaskInfo -TaskName '{TASK_NAME}'; "
        "@{last=$i.LastRunTime.ToString('s'); result=$i.LastTaskResult; "
        "missed=$i.NumberOfMissedRuns; next=$i.NextRunTime.ToString('s')} | ConvertTo-Json -Compress"
    )
    return json.loads(powershell(script))


def staged_count() -> int:
    path = DATA / "staged_emails.json"
    if not path.exists():
        return 0
    return len(json.loads(path.read_text(encoding="utf-8")))


def site_case_count():
    try:
        with urllib.request.urlopen(SITE_JSON, timeout=20) as resp:
            return len(json.loads(resp.read().decode("utf-8")).get("cases", []))
    except Exception:
        return None


def notify(title: str, text: str):
    esc = lambda s: s.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; $n.Visible = $true; "
        f"$n.ShowBalloonTip(20000, '{esc(title)}', '{esc(text)}', [System.Windows.Forms.ToolTipIcon]::Info); "
        "Start-Sleep -Seconds 21; $n.Dispose()"
    )
    powershell(script, timeout=60)


def main():
    now = datetime.now()
    problems = []
    lines = [f"점검 시각: {now:%Y-%m-%d %H:%M}"]

    try:
        info = task_info()
        last = datetime.fromisoformat(info["last"])
        lines.append(f"메일 동기화 마지막 실행: {last:%Y-%m-%d %H:%M} (결과 코드 {info['result']})")
        lines.append(f"다음 예정: {info['next'].replace('T', ' ')[:16]} / 누락 {info['missed']}건")
        if info["result"] not in (0, 267009):
            problems.append(f"마지막 실행 실패(코드 {info['result']})")
        if info["missed"] > 0:
            problems.append(f"누락된 실행 {info['missed']}건")
        if now - last > MAX_SILENCE:
            problems.append(f"{(now - last).days}일 넘게 실행 기록 없음")
    except Exception as exc:
        problems.append(f"작업 스케줄러 조회 실패: {exc}")

    staged = staged_count()
    lines.append(f"미검토 신규 메일: {staged}건")

    cases = site_case_count()
    if cases is None:
        problems.append("사이트(case_studies.json) 접속 실패")
        lines.append("사이트 케이스 수: 확인 실패")
    else:
        lines.append(f"사이트 케이스 수: {cases}건")

    status = "이상 없음" if not problems else "확인 필요: " + "; ".join(problems)
    lines.insert(1, f"상태: {status}")

    report = "\n".join(lines)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "health_report.txt").write_text(report + "\n", encoding="utf-8")
    with (DATA / "health_history.log").open("a", encoding="utf-8") as fh:
        fh.write(f"{now:%Y-%m-%d %H:%M} | {status} | 미검토 {staged}건\n")

    summary = status
    if staged:
        summary += f" / 미검토 메일 {staged}건 - Claude Code에서 '새 메일 확인해줘'"
    notify("헨켈 메일 동기화 점검", summary)


if __name__ == "__main__":
    main()
