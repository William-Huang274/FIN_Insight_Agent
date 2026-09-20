import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

const code = ts.transpileModule(readFileSync(new URL('./vite/src/app/sourceUrl.ts', import.meta.url), 'utf8'),
  {compilerOptions: {module: ts.ModuleKind.ESNext}}).outputText;
const {sourceUrl} = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'));
const path = '/api/v1/research-sessions/01a08ca1-ecac-7913-a9d3-51ebc76a294b/attachments/UPLOAD::a86e6c823b2d436d9b73ef511244b6b1';

test('historical upload links follow the current workbench, preserving document identity', () => {
  for (const origin of ['http://localhost:8766', 'http://127.0.0.1:8765', 'http://[::1]:8080']) {
    assert.equal(sourceUrl(origin + path), path);
  }
  assert.equal(sourceUrl(path), path);
  assert.equal(sourceUrl('http://localhost:8766' + path.replace('::', '%3A%3A')), path.replace('::', '%3A%3A'));
});

test('external originals remain external; unsafe and unrelated relative URLs are rejected', () => {
  const external = 'https://www.hpe.com/report.pdf';
  assert.equal(sourceUrl(external), external);
  assert.equal(sourceUrl('https://example.com' + path), 'https://example.com' + path);
  assert.equal(sourceUrl('http://localhost:8766/other'), 'http://localhost:8766/other');
  for (const unsafe of ['javascript:alert(1)', 'file:///private', '//evil.com', '/other', 'http://user:pass@localhost:8766' + path, undefined]) {
    assert.equal(sourceUrl(unsafe), undefined);
  }
});
