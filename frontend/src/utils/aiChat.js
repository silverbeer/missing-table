/**
 * MT AI web chat (SB-1500): the pure half — safe Markdown, table helpers and
 * error wording for POST /api/ai/chat.
 *
 * Answers come from a model, so they are untrusted text. The renderer escapes
 * every character of HTML first and only then adds back a small, fixed set of
 * tags (strong, em, code, ul/ol/li, p, br, and links to http(s)/mailto). No
 * attribute is ever built from model text except a link's href, which has been
 * escaped and must start with an allowed scheme. That is why the output is
 * safe for v-html without a sanitizer library — the project has none, and
 * `marked` passes raw HTML through.
 */

const HTML_ESCAPES = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

export const escapeHtml = text =>
  String(text ?? '').replace(/[&<>"']/g, ch => HTML_ESCAPES[ch]);

// Matched against the already-escaped URL, so `&` appears as `&amp;`.
const SAFE_URL = /^(https?:\/\/|mailto:)[^\s]+$/i;

/**
 * Inline Markdown on one line of text: `code`, [links](url), **bold**, *em*.
 * Escapes first; the patterns then run over escaped text only.
 */
export function renderInline(text) {
  // Code spans are parked behind a private-use placeholder so the patterns
  // below can't touch them; strip any the input already carries.
  const codeSpans = [];
  const source = String(text ?? '').replace(//g, '');
  let html = escapeHtml(source).replace(/`([^`\n]+)`/g, (_, code) => {
    codeSpans.push(code);
    return `\uE000${codeSpans.length - 1}\uE000`;
  });

  html = html.replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, (_, label, url) =>
    SAFE_URL.test(url)
      ? `<a href="${url}" target="_blank" rel="noopener noreferrer nofollow">${label}</a>`
      : label
  );
  html = html.replace(/\*\*(?=\S)([^\n]*?\S)\*\*/g, '<strong>$1</strong>');
  html = html.replace(
    /(^|[^*\w])\*(?=\S)([^*\n]*?\S)\*(?![*\w])/g,
    '$1<em>$2</em>'
  );

  return html.replace(
    /\uE000(\d+)\uE000/g,
    (_, i) => `<code>${codeSpans[Number(i)]}</code>`
  );
}

const BULLET = /^\s*[-*•]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;
const HEADING = /^\s*#{1,6}\s+(.*)$/;

/**
 * Block-level Markdown: paragraphs (blank-line separated, single newlines kept
 * as <br>), bullet and numbered lists, and headings shown as bold lines.
 */
export function renderMarkdown(text) {
  const lines = String(text ?? '')
    .replace(/\r\n?/g, '\n')
    .split('\n');
  const out = [];
  let paragraph = [];
  let list = null; // { tag: 'ul' | 'ol', items: [] }

  const flushParagraph = () => {
    if (paragraph.length) {
      out.push(`<p>${paragraph.map(renderInline).join('<br>')}</p>`);
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list) {
      const items = list.items.map(i => `<li>${renderInline(i)}</li>`);
      out.push(`<${list.tag}>${items.join('')}</${list.tag}>`);
      list = null;
    }
  };

  for (const line of lines) {
    const bullet = line.match(BULLET);
    const numbered = !bullet && line.match(NUMBERED);
    if (bullet || numbered) {
      const tag = bullet ? 'ul' : 'ol';
      flushParagraph();
      if (list && list.tag !== tag) flushList();
      if (!list) list = { tag, items: [] };
      list.items.push((bullet || numbered)[1]);
      continue;
    }
    flushList();
    if (!line.trim()) {
      flushParagraph();
      continue;
    }
    const heading = line.match(HEADING);
    if (heading) {
      flushParagraph();
      out.push(`<p><strong>${renderInline(heading[1])}</strong></p>`);
      continue;
    }
    paragraph.push(line.trim());
  }
  flushParagraph();
  flushList();
  return out.join('');
}

// "12", "-3", "+5", "1.5", "50%" — what standings and stats columns hold.
const NUMERIC_CELL = /^[+\-−]?\d+(\.\d+)?%?$/;

/**
 * Indexes of columns whose every non-empty cell is a number, so they can be
 * right-aligned. A column with no values at all is not numeric.
 */
export function numericColumns(table) {
  const columns = table?.columns || [];
  const rows = table?.rows || [];
  return columns
    .map((_, col) => {
      const cells = rows
        .map(row => String(row?.[col] ?? '').trim())
        .filter(Boolean);
      return cells.length > 0 && cells.every(c => NUMERIC_CELL.test(c));
    })
    .reduce((acc, numeric, col) => (numeric ? [...acc, col] : acc), []);
}

// Why POST /api/ai/chat failed, keyed by HTTP status.
const CHAT_ERRORS = {
  401: 'Your session has expired. Please log in again.',
  403: "Chat isn't available for your account.",
  404: "That conversation couldn't be found. Start a new chat and try again.",
  429: "You've reached the chat limit for now. Please try again later.",
  502: 'The assistant had trouble answering. Please try again.',
  503: 'Chat is temporarily unavailable. Please try again in a few minutes.',
};

/**
 * The friendly message for a failed chat request. Errors without a status
 * (timeout, offline, expired session) already carry a readable message from
 * the auth store.
 */
export function chatErrorMessage(error) {
  if (error?.status && CHAT_ERRORS[error.status]) {
    return CHAT_ERRORS[error.status];
  }
  if (!error?.status && error?.message) return error.message;
  return 'Something went wrong. Please try again.';
}
