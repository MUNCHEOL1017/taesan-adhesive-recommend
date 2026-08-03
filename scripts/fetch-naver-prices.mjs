import fs from 'node:fs';

// PRODUCT_FAMILIES의 모든 제품명(index.html)과 동일하게 유지해야 합니다.
const PRODUCTS = [
  'LOCTITE EA 9394 AERO',
  'LOCTITE AA 330',
  'LOCTITE EA 3430',
  'LOCTITE EA 9430',
  'LOCTITE EA 9492',
  'LOCTITE 243',
  'LOCTITE 270',
  'LOCTITE 648',
  'LOCTITE 222',
  'LOCTITE 620',
  'LOCTITE 401',
  'LOCTITE 460',
  'LOCTITE 3090',
  'LOCTITE 454',
  'LOCTITE 480',
  'LOCTITE AA 3311',
  'LOCTITE AA 3321',
  'LOCTITE AA 3341',
  'LOCTITE AA 352',
  'LOCTITE AA 3924',
  'LOCTITE SI 5145',
  'LOCTITE SI 5900',
  'LOCTITE SI 5910',
  'LOCTITE SI 5920',
  'LOCTITE SI 598',
  'LOCTITE EA 9483 (구 Hysol 9483)',
  'LOCTITE ECCOBOND FP4531',
  'LOCTITE EA 9309NA AERO',
  'LOCTITE STYCAST US 2350',
  'LOCTITE STYCAST EO 1058',
];

const CLIENT_ID = process.env.NAVER_CLIENT_ID;
const CLIENT_SECRET = process.env.NAVER_CLIENT_SECRET;

if (!CLIENT_ID || !CLIENT_SECRET) {
  console.error('NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 없습니다. (GitHub Secrets 확인)');
  process.exit(1);
}

async function fetchLowest(query) {
  const url = `https://openapi.naver.com/v1/search/shop.json?query=${encodeURIComponent(query)}&display=1&sort=asc`;
  const res = await fetch(url, {
    headers: {
      'X-Naver-Client-Id': CLIENT_ID,
      'X-Naver-Client-Secret': CLIENT_SECRET,
    },
  });
  if (!res.ok) {
    console.error(`[실패] "${query}": HTTP ${res.status}`);
    return null;
  }
  const data = await res.json();
  const item = data.items && data.items[0];
  if (!item) {
    console.warn(`[결과없음] "${query}"`);
    return null;
  }
  return {
    price: Number(item.lprice),
    mallName: item.mallName,
    link: item.link,
    title: item.title.replace(/<[^>]+>/g, ''),
  };
}

const result = {};
for (const name of PRODUCTS) {
  const info = await fetchLowest(name);
  if (info) result[name] = info;
  await new Promise((r) => setTimeout(r, 150)); // API 과호출 방지
}

result._updatedAt = new Date().toISOString();

fs.writeFileSync(new URL('../prices.json', import.meta.url), JSON.stringify(result, null, 2) + '\n');
console.log(`prices.json 저장 완료: ${Object.keys(result).length - 1}개 제품`);
