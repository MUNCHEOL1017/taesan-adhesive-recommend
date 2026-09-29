import fs from 'node:fs';

// index.html을 텍스트로 읽어서 url/tdsUrl/sdsUrl/rohsUrl 값을 전부 뽑아냅니다.
// (JS를 실제로 실행하지 않고 정규식으로만 추출 — 간단하고 안전합니다)
const htmlPath = new URL('../index.html', import.meta.url);
const html = fs.readFileSync(htmlPath, 'utf-8');

const keys = ['url', 'tdsUrl', 'sdsUrl', 'rohsUrl'];
const found = new Map(); // url -> [labels]

for (const key of keys) {
  const re = new RegExp(`${key}:\\s*'([^']+)'`, 'g');
  let m;
  while ((m = re.exec(html))) {
    const url = m[1];
    if (!url.startsWith('http')) continue;
    if (!found.has(url)) found.set(url, []);
    found.get(url).push(key);
  }
}

console.log(`총 ${found.size}개 고유 링크 확인 시작...`);

const results = [];
for (const [url, labels] of found) {
  let status = null;
  let ok = false;
  let error = null;
  try {
    let res = await fetch(url, { method: 'HEAD', redirect: 'follow' });
    if (res.status === 405 || res.status === 403 || res.status === 501) {
      res = await fetch(url, { method: 'GET', redirect: 'follow' });
    }
    status = res.status;
    ok = res.ok;
  } catch (e) {
    error = e.message;
  }
  results.push({ url, labels, status, ok, error });
  await new Promise((r) => setTimeout(r, 150)); // 과호출 방지
}

const failures = results.filter((r) => !r.ok);

console.log(`검사 완료: 총 ${results.length}개 중 실패 ${failures.length}개`);
for (const f of failures) {
  console.log(`- [${f.labels.join(',')}] ${f.url} -> ${f.status ?? 'ERROR'}${f.error ? ' (' + f.error + ')' : ''}`);
}

const report = {
  checkedAt: new Date().toISOString(),
  total: results.length,
  failureCount: failures.length,
  failures,
};

fs.writeFileSync(new URL('../link-check-report.json', import.meta.url), JSON.stringify(report, null, 2) + '\n');

if (failures.length > 0) {
  process.exitCode = 1;
}
