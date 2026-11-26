// Negative-control self-check for the F3 escaping oracle.
//
// It applies the same three safety assertions used by the generated test to
// (a) the real component and (b) a deliberately unsafe component that injects
// the same payload with dangerouslySetInnerHTML.  The real render must pass and
// the unsafe render must fail; otherwise the oracle would be vacuous.
//
// Run with the same NODE_PATH as the experiment:
//   node tests/advanced/experiments/llm_blind/mutation/f3_selfcheck.mjs

import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

import {renderSkills} from '../generated/render_helper.mjs';

const require = createRequire(import.meta.url);
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');

function escapingObligations(html) {
    assert(
        html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'),
        'escaped payload must be present as text',
    );
    assert(!/<script(?:\s|>)/i.test(html), 'no raw script opening tag');
    assert(!html.includes('<script>alert(1)</script>'), 'no raw payload');
}

const safe = renderSkills(['<script>alert(1)</script>']);
escapingObligations(safe);

const Unsafe = () =>
    React.createElement('div', {
        dangerouslySetInnerHTML: {__html: '<span><script>alert(1)</script></span>'},
    });
const unsafe = renderToStaticMarkup(React.createElement(Unsafe));

let rejected = false;
try {
    escapingObligations(unsafe);
} catch {
    rejected = true;
}
assert.equal(rejected, true, 'negative control must be rejected by the oracle');
console.log('F3 self-check: real render passed; unsafe render rejected');
