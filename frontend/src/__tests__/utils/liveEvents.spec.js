/**
 * mergeEventWindow — re-reading chat after the doorbell rings (SB-1329).
 */

import { describe, it, expect } from 'vitest';
import { mergeEventWindow } from '@/utils/liveEvents';

const ev = (id, type = 'message') => ({ id, event_type: type });
const ids = list => list.map(e => e.id);

describe('mergeEventWindow', () => {
  it('adds new chat at the top', () => {
    const merged = mergeEventWindow(
      [ev(2), ev(1, 'goal')],
      [ev(3), ev(2), ev(1, 'goal')],
      50
    );
    expect(ids(merged)).toEqual([3, 2, 1]);
  });

  it('drops a message the fetch no longer returns (deleted)', () => {
    const merged = mergeEventWindow(
      [ev(3), ev(2), ev(1, 'goal')],
      [ev(3), ev(1, 'goal')],
      50
    );
    expect(ids(merged)).toEqual([3, 1]);
  });

  it('keeps older pages outside a full window', () => {
    // limit 2: the fetch covers ids >= 4; 3, 2 and 1 came from "Load more".
    const current = [ev(4), ev(3), ev(2), ev(1)];
    const merged = mergeEventWindow(current, [ev(5), ev(4)], 2);
    expect(ids(merged)).toEqual([5, 4, 3, 2, 1]);
  });

  it('replaces a row with its fetched version', () => {
    const merged = mergeEventWindow(
      [{ id: 1, message: 'old' }],
      [{ id: 1, message: 'new' }],
      50
    );
    expect(merged).toEqual([{ id: 1, message: 'new' }]);
  });

  it('an empty, complete fetch means nothing is left', () => {
    expect(mergeEventWindow([ev(1)], [], 50)).toEqual([]);
  });

  it('tolerates a missing response', () => {
    expect(mergeEventWindow([ev(1)], null, 50)).toEqual([]);
  });
});
