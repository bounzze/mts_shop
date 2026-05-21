import fs from 'fs';
function loadJson(f) {
  const txt = fs.readFileSync(f).toString()
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\/\/[^\n]*/g, '');
  return JSON.parse(txt);
}

function countLeaves(obj, prefix = '') {
  let count = 0;
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
      count += countLeaves(v, prefix + k + '.');
    } else {
      count++;
    }
  }
  return count;
}

function findMissingKeys(en, nl, prefix = '') {
  const missing = [];
  for (const [k, v] of Object.entries(en)) {
    const path = prefix + k;
    if (!(k in nl)) {
      missing.push(path);
    } else if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
      missing.push(...findMissingKeys(v, nl[k], path + '.'));
    }
  }
  return missing;
}

const e = loadJson('locales/en.default.json');
const n = loadJson('locales/nl.json');

const enTotal = countLeaves(e);
const nlTotal = countLeaves(n);
const missing = findMissingKeys(e, n);

console.log(`EN leaf strings: ${enTotal}`);
console.log(`NL leaf strings: ${nlTotal}`);
console.log(`Missing in NL: ${missing.length}`);
if (missing.length > 0 && missing.length <= 50) {
  console.log('\nMissing keys:');
  missing.forEach(k => console.log(' -', k));
} else if (missing.length > 50) {
  console.log('\nFirst 50 missing keys:');
  missing.slice(0, 50).forEach(k => console.log(' -', k));
}
