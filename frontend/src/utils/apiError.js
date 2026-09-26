/**
 * Turning an API error body into something a person can act on (SB-1123).
 *
 * FastAPI's `detail` is three different shapes depending on how the request
 * failed, and the app assumed it was always a string:
 *
 *   raise HTTPException(400, detail="Invalid or expired invite code")
 *     → {"detail": "Invalid or expired invite code"}
 *
 *   a Pydantic validation failure (422)
 *     → {"detail": [{"type": "value_error", "loc": ["body"],
 *                    "msg": "Value error, Password must be at least 12 characters"}]}
 *
 * `new Error(detail)` on the second one produces the string "[object Object]",
 * which is what someone saw after being turned away from signup for a password
 * that was four characters short — with nothing on the form having told them
 * the rule.
 *
 * The rule this keeps: a message the user can act on gets shown; anything
 * describing how the server is built does not. `loc` is a field path into the
 * request model and is never rendered — the message says what to fix, not
 * where in a schema it lives.
 */

/** Pydantic prefixes a custom ValueError with this; it means nothing to a reader. */
const VALUE_ERROR_PREFIX = /^Value error,\s*/;

const cleanMessage = text => {
  if (typeof text !== 'string') return null;
  const trimmed = text.replace(VALUE_ERROR_PREFIX, '').trim();
  return trimmed || null;
};

/**
 * The sentence to show for a failed request.
 *
 * @param {unknown} payload  the parsed response body, or anything at all —
 *   a body that failed to parse, an empty response and `undefined` are all
 *   ordinary here and produce the fallback.
 * @param {string} fallback  what to say when the body says nothing usable.
 * @returns {string}
 */
export const errorMessage = (payload, fallback = 'Something went wrong.') => {
  const detail = payload?.detail;

  // HTTPException(detail="...") — the common, deliberate case.
  const direct = cleanMessage(detail);
  if (direct) return direct;

  // A 422: one entry per field that failed. Several can fail at once, and a
  // reader fixing a form wants all of them, not the first.
  if (Array.isArray(detail)) {
    const messages = detail
      .map(entry => cleanMessage(entry?.msg))
      .filter(Boolean);
    if (messages.length > 0) return messages.join(' ');
  }

  // A single error object, which some handlers send instead of a list.
  if (detail && typeof detail === 'object') {
    const single = cleanMessage(detail.msg) || cleanMessage(detail.message);
    if (single) return single;
  }

  // Some endpoints answer with {message} rather than {detail}.
  const message = cleanMessage(payload?.message);
  if (message) return message;

  // Unrecognised shape. Never stringify it — that is the bug this replaces.
  return fallback;
};

/**
 * Read an error message off a fetch Response.
 *
 * A failing response is not guaranteed to hold JSON — a gateway timeout or a
 * proxy error page will not — so parsing is allowed to fail and falls through
 * to the fallback.
 */
export const responseErrorMessage = async (response, fallback) => {
  try {
    return errorMessage(await response.json(), fallback);
  } catch {
    return fallback;
  }
};
