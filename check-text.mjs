import fs from 'fs';

const files = [
  'sections/header-group.json',
  'sections/footer-group.json',
  'templates/index.json',
  'templates/collection.json',
  'templates/product.json',
  'templates/page.json',
  'templates/404.json',
  'templates/cart.json',
  'templates/search.json'
].filter(f => fs.existsSync(f));

for (const f of files) {
  const txt = fs.readFileSync(f).toString().replace(/\/\*[\s\S]*?\*\//g, '');
  const re = /"text"\s*:\s*"([^"]{3,})"/g;
  let m;
  const found = [];
  while ((m = re.exec(txt)) !== null) {
    const clean = m[1].replace(/<[^>]+>/g, '').replace(/\{\{[^}]+\}\}/g, '{{…}}').trim();
    if (clean.length > 2) found.push(clean.substring(0, 100));
  }
  if (found.length) {
    console.log('\n' + f + ':');
    found.forEach(s => console.log('  ' + s));
  }
}
