import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import test from 'node:test';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const ts = require('typescript');
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
const source = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src/components/skills/SkillTagPicker.tsx');
// Transpile the actual component without rewriting its rendering expressions.
const code = ts.transpileModule(fs.readFileSync(source, 'utf8'), {
    compilerOptions: {jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
    fileName: source,
}).outputText;
const componentModule = {exports: {}};
const componentRequire = id => id.endsWith('.css') ? {} : require(id);
new Function('require', 'module', 'exports', code)(componentRequire, componentModule, componentModule.exports);
const SkillTagPicker = componentModule.exports.default;
const render = value => renderToStaticMarkup(React.createElement(SkillTagPicker, {value, onChange() {}}));

test('FP-SEC-3 actual component renders the required script string as text', () => {
    const html = render(['<script>alert(1)</script>']);
    assert(html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
    assert(!/<script(?:\s|>)/i.test(html));
    assert(!html.includes('aria-label="移除 <script>'));
});

test('FP-SEC-3 ordinary Unicode and quotes survive text rendering', () => {
    const html = render(['中文 Résumé 🙂', 'C++ & "SQL"']);
    assert(html.includes('中文 Résumé 🙂'));
    assert(html.includes('C++ &amp; &quot;SQL&quot;'));
    assert(html.includes('aria-label="移除 C++ &amp; &quot;SQL&quot;"'));
});

test('skill picker label points to the actual input', () => {
    const html = render(['python']);
    const labelId = html.match(/<label for="([^"]+)"/)[1];
    assert(html.includes(`id="${labelId}"`));
    assert(html.includes('aria-label="已选技能"'));
    assert(html.includes('aria-label="移除 python"'));
});
