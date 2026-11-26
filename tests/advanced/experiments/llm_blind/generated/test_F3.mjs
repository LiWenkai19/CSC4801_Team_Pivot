/**
 * F3 — SkillTagPicker HTML-escaping behaviour (FP-SEC-3).
 *
 * Generated blind from contracts/F3.md. Every expected escaped fragment below is
 * hand-calculated from the contract's escaping table (§3.1 and §4):
 *
 *     <  ->  &lt;
 *     >  ->  &gt;
 *     &  ->  &amp;
 *     "  ->  &quot;
 *     '  ->  &#x27;   (an equivalent numeric reference is allowed by §3.1)
 *
 * It was not derived from the component implementation, which was not read.
 *
 * PARTITION MAP (contract §5)
 * ---------------------------
 * Valid
 *   V1  ordinary ASCII/Unicode names, several at once:
 *       ['中文 résumé 🙂', 'c++'].
 *   V2  HTML-looking ordinary text that must stay text, not become markup:
 *       ['<b>bold</b>'].
 * Boundary
 *   B1  empty list [] (contract §4.4: renders the picker, no exception).
 *   B2  a single-character skill ['§'].
 *   B3  names made only of one metacharacter: '<', '>', '"', '&', "'".
 * Invalid / hostile
 *   H1  script tag: ['<script>alert(1)</script>'].
 *   H2  closing tag: ['</script>'].
 *   H3  mixed-case HTML: ['<ScRiPt>alert(1)</ScRiPt>'].
 *   H4  quoted attribute breakout: ['onmouseover="x"'].
 *   H5  ampersand injection: ['a&b'].
 *   H6  literal entity text: ['&lt;'] (must become &amp;lt;, not be decoded).
 *
 * HAND-CALCULATED FRAGMENTS (contract §4)
 * ---------------------------------------
 * H1  '<script>alert(1)</script>'
 *     '<' -> '&lt;' at the opening and at the closing tag; '>' -> '&gt;' at
 *     both; letters, digits, '(' ')' and '/' are not escaped by React.
 *     => &lt;script&gt;alert(1)&lt;/script&gt;
 *     and no /<script(?:\s|>)/i or raw '<script>alert(1)</script>' may remain.
 * H2  '</script>'
 *     '<' -> '&lt;', '>' -> '&gt;', '/' unchanged.
 *     => &lt;/script&gt;
 * H3  '<ScRiPt>alert(1)</ScRiPt>'
 *     '<' -> '&lt;', '>' -> '&gt;'; escaping itself does not change letter case,
 *     but the component may normalise display case (A1), so compare
 *     case-insensitively: after lowercasing => &lt;script&gt;alert(1)&lt;/script&gt;.
 * H4  'onmouseover="x"'
 *     each '"' -> '&quot;'; '=' and letters unchanged.
 *     => onmouseover=&quot;x&quot;
 * H5  'a&b'
 *     '&' -> '&amp;'; 'a' and 'b' unchanged.
 *     => a&amp;b
 * H6  '&lt;' (the four literal characters & l t ;)
 *     the single '&' -> '&amp;'; 'lt;' unchanged.
 *     => &amp;lt;
 * B2  '§' and V1's '中文 résumé 🙂' / 'c++' contain none of the five escaped
 *     characters, so they must appear unchanged (case per A1).
 * B3  '<' => &lt;   '>' => &gt;   '"' => &quot;   '&' => &amp;   "'" => &#x27;.
 *
 * AMBIGUITIES RECORDED (contract §6) AND RESOLUTIONS
 * -------------------------------------------------
 * A1  Display normalisation (lowercasing or catalogue spelling) is unknown.
 *     No whole-HTML assertion is made; comparisons are case-insensitive where a
 *     value may be normalised (H3, V1). H1/H2/H4/H5 are already lower-case.
 * A2  Attribute order, whitespace and CSS class names are not asserted.
 * A3  The remove control's element/tag layout is not fixed by the requirements,
 *     so assertions require the escaped value to occur somewhere and never a
 *     specific <button>/aria-label layout. Where the component does copy a name
 *     into a quoted attribute, that copy is checked for escaping (H4).
 * A4  renderToStaticMarkup never executes JavaScript: "not executable" is shown
 *     by absence of raw markup, not by running a browser.
 * A5  Typing/search behaviour is outside F3; only the controlled `value` prop is
 *     exercised (the helper passes a no-op onChange).
 * A6  '/' is listed as a possible input metacharacter but is not one of the
 *     five characters React escapes (§3.1); no test requires '/' to be escaped.
 * A7  §4.4's "without any tag" is read as "without selected-skill tags", not
 *     "without any HTML element", so B1 asserts only that [] renders without
 *     throwing and returns a non-empty string.
 * A8  §4.1 illustrates aria-label="Remove <name>" while §6.3 says layout is not
 *     fixed; this file follows §6.3 (A3) and never asserts a whole aria-label
 *     string.
 * A9  The contract names frontend/src/components/skills/SkillTagPicker.tsx, but
 *     its calling-convention paragraph (and the provided helper) render the
 *     default export of CandidateSkillPicker.tsx inside LanguageProvider; the
 *     test exercises whatever the sanctioned helper renders.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {renderSkills} from './render_helper.mjs';

test('F3 H1: <script> payload becomes escaped text, never raw markup', () => {
    const html = renderSkills(['<script>alert(1)</script>']);

    // Hand calc H1: angle brackets escaped, |( ) 1 /| unchanged.
    assert.ok(html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
    assert.ok(!/<script(?:\s|>)/i.test(html));
    assert.ok(!html.includes('<script>alert(1)</script>'));
    assert.ok(!html.includes('</script>'));
    // Attribute copy (A3): no raw '<' may leak into a quoted aria-label value.
    assert.ok(!/aria-label="[^"]*<[^"]*"/.test(html));
});

test('F3 H2: a literal closing script tag cannot appear', () => {
    const html = renderSkills(['</script>']);

    // Hand calc H2: '<' -> &lt;, '>' -> &gt;, '/' is not escaped.
    assert.ok(html.includes('&lt;/script&gt;'));
    assert.ok(!html.includes('</script>'));
});

test('F3 H3: mixed-case HTML is escaped despite display normalisation', () => {
    const html = renderSkills(['<ScRiPt>alert(1)</ScRiPt>']);

    // Hand calc H3; lowercased because the component may normalise case (A1).
    assert.ok(html.toLowerCase().includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
    assert.ok(!/<script(?:\s|>)/i.test(html));
    assert.ok(!html.toLowerCase().includes('script>alert(1)</script>'));
    assert.ok(!html.includes('<ScRiPt>alert(1)</ScRiPt>'));
});

test('F3 H4: a double quote cannot break out of an attribute', () => {
    const html = renderSkills(['onmouseover="x"']);

    // Hand calc H4: each '"' -> &quot;.
    assert.ok(html.includes('onmouseover=&quot;x&quot;'));
    assert.ok(!html.includes('onmouseover="x"'));

    // A3: tag layout is not fixed. Only if the component copies the name into
    // quoted attributes do we require that copy to contain the escaped form.
    const attributeValues = [...html.matchAll(/="([^"]*)"/g)].map(match => match[1]);
    for (const value of attributeValues) {
        if (!value.includes('onmouseover')) continue;
        assert.ok(value.includes('onmouseover=&quot;x&quot;'), `attribute copy left unescaped: ${value}`);
        assert.ok(!value.includes('onmouseover="x"'), `raw payload in attribute: ${value}`);
    }
});

test('F3 H5: ampersand is escaped exactly once', () => {
    const html = renderSkills(['a&b']);

    // Hand calc H5: '&' -> &amp;.
    assert.ok(html.includes('a&amp;b'));
    assert.ok(!html.includes('a&b'));
});

test('F3 H6: literal entity text is escaped, not decoded', () => {
    const html = renderSkills(['&lt;']);

    // Hand calc H6: the literal '&' -> &amp;, 'lt;' unchanged. Decoding the
    // literal entity to '<' would re-escape as &lt; and break this assertion,
    // so the positive fragment alone fixes the required transformation.
    assert.ok(html.includes('&amp;lt;'));
});

test('F3 B1: empty value renders without a selected tag or exception', () => {
    let html;
    assert.doesNotThrow(() => {
        html = renderSkills([]);
    });
    assert.equal(typeof html, 'string');
    assert.ok(html.length > 0);
});

test('F3 B2: a single-character skill is preserved', () => {
    const html = renderSkills(['§']);

    // '§' is none of < > & " ', so no escaping applies (contract §3.1).
    assert.ok(html.includes('§'));
});

test('F3 B3: metacharacter-only names are escaped', () => {
    const cases = [
        ['<', '&lt;'],
        ['>', '&gt;'],
        ['"', '&quot;'],
        ['&', '&amp;'],
    ];
    for (const [name, escaped] of cases) {
        const html = renderSkills([name]);
        assert.ok(html.includes(escaped), `${JSON.stringify(name)} should be emitted as ${escaped}`);
    }

    // Hand calc: "'" -> &#x27;; §3.1 also accepts an equivalent numeric reference.
    const apostropheHtml = renderSkills(["'"]);
    assert.match(apostropheHtml, /&#(?:x0*27|0*39);/i);
});

test('F3 V1: ordinary Unicode and several skills survive as visible text', () => {
    const html = renderSkills(['中文 résumé 🙂', 'c++']);

    // None of these characters need escaping; only case may be normalised (A1).
    const lower = html.toLowerCase();
    assert.ok(lower.includes('中文 résumé 🙂'));
    assert.ok(lower.includes('c++'));
});

test('F3 V2: tag-like ordinary text becomes one text node, not an element', () => {
    const html = renderSkills(['<b>bold</b>']);

    // Hand calc: '<' -> &lt;, '>' -> &gt;, '/' unchanged. If the name were ever
    // injected as markup or as a React element, the raw payload would reappear.
    assert.ok(html.includes('&lt;b&gt;bold&lt;/b&gt;'));
    assert.ok(!html.includes('<b>bold</b>'));
});
