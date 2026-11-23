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
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src');
const sourceModules = new Map();

// Load the actual component and its language provider without rewriting either one.
function loadSource(file) {
    if (sourceModules.has(file)) return sourceModules.get(file).exports;
    const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
        compilerOptions: {jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
        fileName: file,
    }).outputText;
    const sourceModule = {exports: {}};
    sourceModules.set(file, sourceModule);
    const sourceRequire = id => {
        if (id.endsWith('.css')) return {};
        if (!id.startsWith('.')) return require(id);
        const target = path.resolve(path.dirname(file), id);
        const candidate = ['.ts', '.tsx'].map(ext => target + ext).find(fs.existsSync);
        if (!candidate) throw new Error(`Cannot resolve ${id} from ${file}`);
        return loadSource(candidate);
    };
    new Function('require', 'module', 'exports', code)(sourceRequire, sourceModule, sourceModule.exports);
    return sourceModule.exports;
}

const CandidateSkillPicker = loadSource(path.join(src, 'components/skills/CandidateSkillPicker.tsx')).default;
const LanguageProvider = loadSource(path.join(src, 'i18n/LanguageProvider.tsx')).default;
const render = value => renderToStaticMarkup(React.createElement(
    LanguageProvider,
    null,
    React.createElement(CandidateSkillPicker, {value, onChange() {}}),
));

test('FP-SEC-3 actual component renders the required script string as text', () => {
    const html = render(['<script>alert(1)</script>']);
    assert(html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
    assert(!/<script(?:\s|>)/i.test(html));
    assert(!html.includes('aria-label="Remove <script>'));
});

test('FP-SEC-3 ordinary Unicode and quotes survive text rendering', () => {
    const html = render(['中文 Résumé 🙂', 'C++ & "SQL"']);
    assert(html.includes('中文 résumé 🙂'));
    assert(html.includes('c++ &amp; &quot;sql&quot;'));
    assert(html.includes('aria-label="Remove c++ &amp; &quot;sql&quot;"'));
});

test('skill picker label points to the actual input', () => {
    const html = render(['python']);
    const labelId = html.match(/<label for="([^"]+)"/)[1];
    assert(html.includes(`id="${labelId}"`));
    assert(html.includes('aria-label="Selected Skills"'));
    assert(html.includes('aria-label="Remove Python"'));
});
