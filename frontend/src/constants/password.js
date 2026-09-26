/**
 * The password policy, mirrored from the backend (SB-640, surfaced SB-1123).
 *
 * `backend/constants/passwords.py` is the authority — it also blocks common
 * bases and passwords containing the username, which need the server. This
 * copy exists so the form can state the rule up front and catch the commonest
 * failure without a round trip, which is what someone needed when a signup
 * came back saying only "[object Object]".
 *
 * Change one, change the other. A client floor higher than the server's locks
 * people out of a password the server would accept; lower, and the form
 * promises something the server refuses.
 */
export const MIN_PASSWORD_LENGTH = 12;

/**
 * Said on the form before submit, not only after a rejection.
 *
 * Named for the rule rather than the field: a constant called PASSWORD_*
 * holding a string trips the secret scanner's keyword heuristic, and an
 * allowlist pragma on a line that holds no secret is the wrong signal to
 * leave for whoever reads it next.
 */
export const LENGTH_HINT = `At least ${MIN_PASSWORD_LENGTH} characters. Length matters more than symbols.`;

/**
 * The reason this password cannot be set, or null when the client can see
 * nothing wrong. The server still has the final say.
 */
export const passwordProblem = password => {
  if (!password) return 'Enter a password';
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters`;
  }
  return null;
};
