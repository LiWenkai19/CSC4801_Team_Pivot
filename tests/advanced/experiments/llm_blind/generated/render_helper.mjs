// Render helper for the blind-generated F3 test.
//
// Written by the experiment owner as harness, not as an oracle. It uses the same
// calling convention as frontend/tests/rendering.unit.mjs: transpile the real TSX
// source with the `typescript` package, load it through a tiny CommonJS loader,
// and render with react-dom/server. The component source is read at runtime; the
// generation agent was forbidden to read it.

import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const ts = require('typescript');
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.resolve(here, '../../../../../frontend/src');
const sourceModules = new Map();

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

export function renderSkills(value) {
    return renderToStaticMarkup(React.createElement(
        LanguageProvider,
        null,
        React.createElement(CandidateSkillPicker, {value, onChange() {}}),
    ));
}
