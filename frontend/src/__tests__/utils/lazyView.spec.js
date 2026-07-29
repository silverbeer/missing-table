import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { h } from 'vue';
import {
  lazyView,
  isChunkLoadError,
  reloadForStaleChunk,
  installChunkErrorHandler,
} from '@/utils/lazyView';

const Real = { name: 'Real', render: () => h('div', 'loaded') };

/** sessionStorage stub we can make fail on demand (private mode, blocked cookies). */
function makeStorage({ blocked = false } = {}) {
  const map = new Map();
  return {
    getItem: key => {
      if (blocked) throw new Error('blocked');
      return map.has(key) ? map.get(key) : null;
    },
    setItem: (key, value) => {
      if (blocked) throw new Error('blocked');
      map.set(key, String(value));
    },
  };
}

let reloadSpy;

beforeEach(() => {
  reloadSpy = vi.fn();
  // happy-dom's location.reload isn't configurable in place — replace location.
  delete window.location;
  window.location = { reload: reloadSpy, href: 'https://missingtable.com/' };
  window.sessionStorage.clear?.();
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('isChunkLoadError', () => {
  it.each([
    'Failed to fetch dynamically imported module: https://x/ProfileRouter-a1.js',
    'error loading dynamically imported module',
    'Importing a module script failed.',
    "Expected a JavaScript module script but the server responded with a MIME type of 'text/html' is not a valid JavaScript MIME type",
    'Unable to preload CSS for /assets/Foo.css',
    'ChunkLoadError: Loading chunk 4 failed',
  ])('matches %s', message => {
    expect(isChunkLoadError(new Error(message))).toBe(true);
  });

  it('does not match an ordinary runtime error', () => {
    expect(isChunkLoadError(new TypeError('x is not a function'))).toBe(false);
  });

  it('tolerates null and non-Error values', () => {
    expect(isChunkLoadError(null)).toBe(false);
    expect(isChunkLoadError('ChunkLoadError')).toBe(true);
  });
});

describe('reloadForStaleChunk', () => {
  it('reloads on the first call', () => {
    expect(reloadForStaleChunk(makeStorage())).toBe(true);
    expect(reloadSpy).toHaveBeenCalledTimes(1);
  });

  it('refuses a second reload inside the cooldown — no reload loop', () => {
    const storage = makeStorage();
    expect(reloadForStaleChunk(storage)).toBe(true);
    expect(reloadForStaleChunk(storage)).toBe(false);
    expect(reloadSpy).toHaveBeenCalledTimes(1);
  });

  it('reloads again once the cooldown has elapsed', () => {
    const storage = makeStorage();
    const start = Date.now();
    const nowSpy = vi.spyOn(Date, 'now');

    nowSpy.mockReturnValue(start);
    expect(reloadForStaleChunk(storage)).toBe(true);

    nowSpy.mockReturnValue(start + 31_000);
    expect(reloadForStaleChunk(storage)).toBe(true);
    expect(reloadSpy).toHaveBeenCalledTimes(2);
  });

  it('does not reload when storage is unavailable (cannot record the attempt)', () => {
    expect(reloadForStaleChunk(makeStorage({ blocked: true }))).toBe(false);
    expect(reloadSpy).not.toHaveBeenCalled();
  });
});

describe('lazyView', () => {
  it('renders the component when the chunk loads', async () => {
    const Comp = lazyView(() => Promise.resolve(Real), 'Real');
    const wrapper = mount({ render: () => h(Comp) });
    await flushPromises();
    expect(wrapper.text()).toContain('loaded');
  });

  it('retries once and succeeds on a transient failure', async () => {
    const loader = vi
      .fn()
      .mockRejectedValueOnce(new Error('network hiccup'))
      .mockResolvedValue(Real);

    const wrapper = mount({ render: () => h(lazyView(loader, 'Real')) });
    await flushPromises();
    await flushPromises();

    expect(loader).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain('loaded');
    expect(reloadSpy).not.toHaveBeenCalled();
  });

  it('reloads the page when a chunk stays missing after the retry', async () => {
    const chunkError = new Error(
      'Failed to fetch dynamically imported module: /assets/ProfileRouter-a1.js'
    );
    const loader = vi.fn().mockRejectedValue(chunkError);

    mount({ render: () => h(lazyView(loader, 'ProfileRouter')) });
    await flushPromises();
    await flushPromises();
    await flushPromises();

    expect(loader).toHaveBeenCalledTimes(2);
    expect(reloadSpy).toHaveBeenCalledTimes(1);
  });

  it('shows a visible error — never a blank pane — once reloading is exhausted', async () => {
    // Pre-arm the cooldown so the reload path declines and we fall through.
    reloadForStaleChunk();
    reloadSpy.mockClear();

    const loader = vi
      .fn()
      .mockRejectedValue(
        new Error('Failed to fetch dynamically imported module: /assets/x.js')
      );

    const wrapper = mount({
      render: () => h(lazyView(loader, 'ProfileRouter')),
    });
    await flushPromises();
    await flushPromises();
    await flushPromises();

    expect(reloadSpy).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="lazy-view-error"]').exists()).toBe(true);
    expect(wrapper.text()).toContain("This section didn't load");
    expect(wrapper.text()).toContain('ProfileRouter');
  });

  it('error state offers a working reload button', async () => {
    reloadForStaleChunk();
    reloadSpy.mockClear();

    const loader = vi.fn().mockRejectedValue(new Error('ChunkLoadError: nope'));
    const wrapper = mount({ render: () => h(lazyView(loader, 'AdminPanel')) });
    await flushPromises();
    await flushPromises();
    await flushPromises();

    await wrapper
      .find('[data-testid="lazy-view-error"] button')
      .trigger('click');
    expect(reloadSpy).toHaveBeenCalledTimes(1);
  });

  it('surfaces the error for a non-chunk failure instead of reloading', async () => {
    const loader = vi
      .fn()
      .mockRejectedValue(new SyntaxError('unexpected token in component'));

    const wrapper = mount({ render: () => h(lazyView(loader, 'MatchesView')) });
    await flushPromises();
    await flushPromises();
    await flushPromises();

    expect(reloadSpy).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="lazy-view-error"]').exists()).toBe(true);
  });
});

describe('installChunkErrorHandler', () => {
  it('reloads when vite reports a preload failure', () => {
    const listeners = {};
    const target = {
      addEventListener: (name, fn) => {
        listeners[name] = fn;
      },
    };

    installChunkErrorHandler(target);
    expect(listeners['vite:preloadError']).toBeTypeOf('function');

    listeners['vite:preloadError']({ payload: new Error('preload failed') });
    expect(reloadSpy).toHaveBeenCalledTimes(1);
  });
});
