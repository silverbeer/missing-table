/**
 * Async-component loader that fails loudly instead of rendering nothing.
 *
 * Vue's bare `defineAsyncComponent(() => import('./Foo.vue'))` renders an empty
 * comment node when the chunk fetch rejects — no spinner, no message. The
 * surrounding app keeps painting, so the user sees a blank pane with a working
 * nav and no clue anything broke (SB-439: the Profile tab).
 *
 * The chunk fetch rejects routinely in production: every merge to main ships a
 * new frontend image with new content-hashed filenames, so a tab opened before
 * the deploy asks for a `Foo-<oldhash>.js` that no longer exists and gets a 404.
 * The service worker auto-updates (see usePwaUpdate) but only once it notices
 * the new build — a tab can hit a dead chunk before that happens.
 *
 * So: retry once (covers a transient network blip), then reload the page once
 * (covers the stale-deploy case, which a reload always fixes), then — if the
 * reload didn't help — show a visible error with a manual retry button rather
 * than a blank pane.
 */
import { defineAsyncComponent, h } from 'vue';

// Session-scoped guard so a genuinely broken chunk can't reload-loop the tab.
const RELOAD_KEY = 'mt:chunk-reload-at';
const RELOAD_COOLDOWN_MS = 30_000;

/**
 * True for the errors browsers throw when a dynamic import can't be fetched or
 * parsed. The wording differs per engine, hence the loose match.
 */
export function isChunkLoadError(error) {
  const message = String(error?.message || error || '');
  return (
    /Failed to fetch dynamically imported module/i.test(message) ||
    /error loading dynamically imported module/i.test(message) ||
    /Importing a module script failed/i.test(message) ||
    /'text\/html' is not a valid JavaScript MIME type/i.test(message) ||
    /Unable to preload CSS/i.test(message) ||
    /ChunkLoadError/i.test(message)
  );
}

/**
 * Reload once per cooldown window. Returns false when a reload was already
 * attempted recently, so callers can fall through to a visible error instead.
 */
export function reloadForStaleChunk(storage = window.sessionStorage) {
  let last = 0;
  try {
    last = Number(storage.getItem(RELOAD_KEY)) || 0;
  } catch {
    // Storage blocked (private mode, cookie policy) — treat as never reloaded.
  }

  // Date.now() is fine here: this is runtime behavior, not a build artifact.
  const now = Date.now();
  if (last && now - last < RELOAD_COOLDOWN_MS) return false;

  try {
    storage.setItem(RELOAD_KEY, String(now));
  } catch {
    // If we can't record the attempt we'd risk a reload loop — don't reload.
    return false;
  }

  window.location.reload();
  return true;
}

function renderLoading() {
  return h('div', { class: 'flex items-center justify-center py-16' }, [
    h('div', {
      class:
        'h-10 w-10 animate-spin rounded-full border-4 border-gray-200 border-t-blue-500',
      role: 'status',
      'aria-label': 'Loading',
    }),
  ]);
}

function renderError(name) {
  return h(
    'div',
    {
      class:
        'mx-auto my-10 max-w-md rounded-lg border border-gray-200 bg-gray-50 p-6 text-center dark:border-gray-700 dark:bg-gray-800',
      'data-testid': 'lazy-view-error',
    },
    [
      h(
        'h3',
        {
          class: 'mb-2 text-lg font-semibold text-gray-900 dark:text-gray-100',
        },
        "This section didn't load"
      ),
      h(
        'p',
        { class: 'mb-4 text-sm text-gray-600 dark:text-gray-300' },
        'The app was updated or the connection dropped. Reloading usually fixes it.'
      ),
      h(
        'button',
        {
          class:
            'rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700',
          onClick: () => window.location.reload(),
        },
        'Reload page'
      ),
      h(
        'p',
        { class: 'mt-3 text-xs text-gray-400' },
        `Failed to load: ${name}`
      ),
    ]
  );
}

/**
 * Wrap a dynamic import for use as an async component.
 *
 * @param {() => Promise<any>} loader dynamic import, e.g. `() => import('./Foo.vue')`
 * @param {string} name component name, shown in the error state and logs
 */
export function lazyView(loader, name = 'view') {
  return defineAsyncComponent({
    loader,
    // Only show the spinner if loading is actually slow — avoids a flash on
    // fast connections where the chunk arrives in a few ms.
    delay: 200,
    loadingComponent: { name: `${name}Loading`, render: renderLoading },
    errorComponent: { name: `${name}Error`, render: () => renderError(name) },
    timeout: 20_000,
    onError(error, retry, fail, attempts) {
      const chunkError = isChunkLoadError(error);
      console.error(
        `[lazyView] ${name} failed to load (attempt ${attempts})`,
        error
      );

      // Attempt 1: a plain retry handles transient network failures.
      if (attempts <= 1) {
        retry();
        return;
      }

      // Attempt 2+: the asset is genuinely gone — almost always a deploy that
      // rotated the hashed filenames. A reload fetches the new index.html and
      // its new chunk names.
      if (chunkError && reloadForStaleChunk()) return;

      fail();
    },
  });
}

/**
 * Vite emits `vite:preloadError` when a modulepreload for a chunk fails, which
 * can happen before any async component's own loader rejects. Same remedy.
 */
export function installChunkErrorHandler(target = window) {
  target.addEventListener('vite:preloadError', event => {
    console.error('[lazyView] vite:preloadError', event?.payload);
    // Let the reload attempt happen; if it's on cooldown the component-level
    // error state takes over.
    reloadForStaleChunk();
  });
}
