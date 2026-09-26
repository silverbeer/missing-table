/**
 * Reading an API error body (SB-1123).
 *
 * The bug this replaces: `new Error(body.detail)` on a 422, whose detail is a
 * list of objects, rendered "[object Object]" to someone whose password was
 * four characters too short.
 */

import { describe, it, expect } from 'vitest';
import { errorMessage, responseErrorMessage } from '@/utils/apiError';

describe('errorMessage — the shapes FastAPI actually sends', () => {
  it('passes through a plain string detail', () => {
    expect(errorMessage({ detail: 'Invalid or expired invite code' })).toBe(
      'Invalid or expired invite code'
    );
  });

  it('reads the message out of a 422 list — the case that broke signup', () => {
    const body = {
      detail: [
        {
          type: 'value_error',
          loc: ['body'],
          msg: 'Value error, Password must be at least 12 characters',
          input: {},
        },
      ],
    };
    expect(errorMessage(body)).toBe('Password must be at least 12 characters');
  });

  it('never renders [object Object]', () => {
    const body = { detail: [{ msg: 'Too short', loc: ['body', 'password'] }] };
    expect(errorMessage(body)).not.toContain('[object Object]');
  });

  it('joins every field that failed, not just the first', () => {
    const body = {
      detail: [
        { msg: 'Password must be at least 12 characters' },
        { msg: 'Username must be 3-50 characters long' },
      ],
    };
    expect(errorMessage(body)).toBe(
      'Password must be at least 12 characters Username must be 3-50 characters long'
    );
  });

  it('strips the "Value error," prefix Pydantic adds', () => {
    expect(errorMessage({ detail: [{ msg: 'Value error, Too short' }] })).toBe(
      'Too short'
    );
  });

  it('never leaks loc — a field path into the request model', () => {
    const body = {
      detail: [{ msg: 'Too short', loc: ['body', 'password'], type: 'x' }],
    };
    const text = errorMessage(body);
    expect(text).not.toContain('body');
    expect(text).not.toContain('password');
    expect(text).not.toContain('loc');
  });

  it('reads a single error object', () => {
    expect(errorMessage({ detail: { msg: 'Nope' } })).toBe('Nope');
  });

  it('falls back to {message} when there is no detail', () => {
    expect(errorMessage({ message: 'Server busy' })).toBe('Server busy');
  });
});

describe('errorMessage — when the body says nothing usable', () => {
  const FALLBACK = 'Signup failed';

  it('falls back for an empty body, null and undefined', () => {
    expect(errorMessage({}, FALLBACK)).toBe(FALLBACK);
    expect(errorMessage(null, FALLBACK)).toBe(FALLBACK);
    expect(errorMessage(undefined, FALLBACK)).toBe(FALLBACK);
  });

  it('falls back rather than stringifying an unrecognised shape', () => {
    const weird = { detail: { code: 42, nested: { deep: true } } };
    const text = errorMessage(weird, FALLBACK);
    expect(text).toBe(FALLBACK);
    expect(text).not.toContain('[object Object]');
  });

  it('falls back for an empty list and for blank messages', () => {
    expect(errorMessage({ detail: [] }, FALLBACK)).toBe(FALLBACK);
    expect(errorMessage({ detail: '   ' }, FALLBACK)).toBe(FALLBACK);
    expect(errorMessage({ detail: [{ msg: '' }] }, FALLBACK)).toBe(FALLBACK);
  });

  it('has a fallback of its own when none is given', () => {
    expect(errorMessage({})).toBeTruthy();
  });
});

describe('responseErrorMessage', () => {
  it('reads the message off a JSON response', async () => {
    const response = { json: async () => ({ detail: 'Nope' }) };
    expect(await responseErrorMessage(response, 'fallback')).toBe('Nope');
  });

  it('falls back when the body is not JSON — a gateway error page', async () => {
    const response = {
      json: async () => {
        throw new SyntaxError('Unexpected token <');
      },
    };
    expect(await responseErrorMessage(response, 'Login failed')).toBe(
      'Login failed'
    );
  });
});
