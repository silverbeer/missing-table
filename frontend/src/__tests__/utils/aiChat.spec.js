/**
 * MT AI web chat helpers (SB-1500): safe Markdown, numeric columns, error text.
 *
 * Answers are model output and so untrusted; everything rendered with v-html
 * goes through renderMarkdown / renderInline, which must never let HTML out.
 */

import { describe, it, expect } from 'vitest';
import {
  escapeHtml,
  renderInline,
  renderMarkdown,
  numericColumns,
  chatErrorMessage,
} from '@/utils/aiChat';

describe('escapeHtml', () => {
  it('escapes every HTML-significant character', () => {
    expect(escapeHtml(`<a href="x" onclick='y'>&</a>`)).toBe(
      '&lt;a href=&quot;x&quot; onclick=&#39;y&#39;&gt;&amp;&lt;/a&gt;'
    );
  });

  it('treats null and undefined as empty', () => {
    expect(escapeHtml(null)).toBe('');
    expect(escapeHtml(undefined)).toBe('');
  });
});

describe('renderInline', () => {
  it('renders bold, emphasis and code', () => {
    expect(renderInline('**IFA** won *again* with `4-3-3`')).toBe(
      '<strong>IFA</strong> won <em>again</em> with <code>4-3-3</code>'
    );
  });

  it('does not treat arithmetic asterisks as emphasis', () => {
    expect(renderInline('3 * 4 = 12')).toBe('3 * 4 = 12');
  });

  it('links http(s) and mailto URLs, opening in a new tab', () => {
    expect(renderInline('[MT](https://missingtable.com/a?b=1&c=2)')).toBe(
      '<a href="https://missingtable.com/a?b=1&amp;c=2" target="_blank" rel="noopener noreferrer nofollow">MT</a>'
    );
    expect(renderInline('[mail](mailto:a@b.co)')).toContain(
      'href="mailto:a@b.co"'
    );
  });

  it('drops links with any other scheme, keeping the label', () => {
    expect(renderInline('[click](javascript:alert(1))')).not.toContain('<a');
    expect(renderInline('[click](data:text/html,x)')).toBe('click');
  });

  it('cannot break out of an href with a quote', () => {
    const html = renderInline('[x](https://a.com/"onmouseover="alert(1))');
    expect(html).not.toContain('"onmouseover');
  });

  it('escapes HTML inside bold and code', () => {
    expect(renderInline('**<b>x</b>** `<i>`')).toBe(
      '<strong>&lt;b&gt;x&lt;/b&gt;</strong> <code>&lt;i&gt;</code>'
    );
  });
});

describe('renderMarkdown', () => {
  it('escapes script and event-handler HTML', () => {
    const html = renderMarkdown(
      '<script>alert(1)</script>\n<img src=x onerror="alert(1)">'
    );
    expect(html).not.toContain('<script');
    expect(html).not.toContain('<img');
    expect(html).toContain('&lt;script&gt;');
    expect(html).toContain('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
  });

  it('keeps single newlines as line breaks and splits paragraphs', () => {
    expect(renderMarkdown('one\ntwo\n\nthree')).toBe(
      '<p>one<br>two</p><p>three</p>'
    );
  });

  it('renders bullet and numbered lists', () => {
    expect(renderMarkdown('Next:\n- **Sat** vs NEFC\n- Sun vs FCW')).toBe(
      '<p>Next:</p><ul><li><strong>Sat</strong> vs NEFC</li><li>Sun vs FCW</li></ul>'
    );
    expect(renderMarkdown('1. first\n2. second')).toBe(
      '<ol><li>first</li><li>second</li></ol>'
    );
  });

  it('shows headings as bold lines', () => {
    expect(renderMarkdown('## Standings')).toBe(
      '<p><strong>Standings</strong></p>'
    );
  });

  it('renders nothing for an empty answer', () => {
    expect(renderMarkdown('')).toBe('');
    expect(renderMarkdown(null)).toBe('');
  });
});

describe('numericColumns', () => {
  it('finds columns where every value is a number', () => {
    const table = {
      columns: ['#', 'Team', 'GP', 'GD', 'Pts', 'Form'],
      rows: [
        ['1', 'IFA', '10', '+12', '25', '🟩🟩🟥'],
        ['2', 'NEFC', '10', '-3', '18', '🟨🟩🟩'],
      ],
    };
    expect(numericColumns(table)).toEqual([0, 2, 3, 4]);
  });

  it('does not call an empty column numeric', () => {
    expect(numericColumns({ columns: ['A'], rows: [['']] })).toEqual([]);
    expect(numericColumns({})).toEqual([]);
  });
});

describe('chatErrorMessage', () => {
  it('words each documented status', () => {
    for (const status of [401, 403, 404, 429, 502, 503]) {
      const message = chatErrorMessage({ status, message: 'raw detail' });
      expect(message).not.toBe('raw detail');
      expect(message.length).toBeGreaterThan(0);
    }
    expect(chatErrorMessage({ status: 429 })).toMatch(/limit/i);
  });

  it('passes through status-less messages (timeout, offline)', () => {
    expect(
      chatErrorMessage(new Error('Request timed out. Check your connection.'))
    ).toBe('Request timed out. Check your connection.');
  });

  it('falls back for an unknown status', () => {
    expect(chatErrorMessage({ status: 500, message: 'Traceback' })).toBe(
      'Something went wrong. Please try again.'
    );
  });
});
