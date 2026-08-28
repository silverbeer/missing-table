/**
 * ModalOverlay.vue tests (SB-890).
 *
 * The regression these guard: the match preview could become impossible to
 * close. Its close button was `absolute` on the card, so on a short window,
 * scrolling to read the content carried the only visible exit off-screen —
 * while Escape was unhandled and the page scrolled freely behind.
 *
 * The rule is that no single failure traps anyone: the pinned button, Escape
 * and a backdrop click are three independent ways out.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mount } from '@vue/test-utils';

import ModalOverlay from '@/components/ui/ModalOverlay.vue';

const mountOverlay = (props = {}, slot = '<p>Match details</p>') =>
  mount(ModalOverlay, {
    props,
    slots: { default: slot },
    attachTo: document.body,
  });

// The overlay is teleported to <body>, so it is outside the wrapper's tree.
// Query the document for it.
const $ = sel => document.querySelector(sel);
const overlayEl = () => $('[data-testid="modal-overlay"]');
const closeEl = () => $('[data-testid="modal-close"]');
const fire = (el, type, init = {}) =>
  el.dispatchEvent(
    new (type.startsWith('key') ? KeyboardEvent : MouseEvent)(type, {
      bubbles: true,
      ...init,
    })
  );

beforeEach(() => {
  document.body.style.overflow = '';
  document.body.style.paddingRight = '';
});

afterEach(() => {
  document.body.innerHTML = '';
  document.body.style.overflow = '';
  document.body.style.paddingRight = '';
});

describe('ModalOverlay — three ways out', () => {
  it('closes on the pinned button', async () => {
    const wrapper = mountOverlay();
    fire(closeEl(), 'click');

    expect(wrapper.emitted('close')).toHaveLength(1);
  });

  it('closes on Escape', async () => {
    const wrapper = mountOverlay();
    fire(overlayEl(), 'keydown', { key: 'Escape' });

    expect(wrapper.emitted('close')).toHaveLength(1);
  });

  it('closes on a backdrop click', async () => {
    const wrapper = mountOverlay();
    // A click whose target IS the overlay -- i.e. the backdrop, not the card.
    overlayEl().dispatchEvent(new MouseEvent('click', { bubbles: false }));

    expect(wrapper.emitted('close')).toHaveLength(1);
  });

  it('does not close when the card itself is clicked', async () => {
    const wrapper = mountOverlay();
    fire($('[data-testid="modal-overlay"] p'), 'click');

    expect(wrapper.emitted('close')).toBeUndefined();
  });
});

describe('ModalOverlay — the close button stays reachable', () => {
  it('pins the close button to the viewport, not the scrolling card', () => {
    // This is the actual bug. `absolute` positioned the button against the
    // card, so it left the viewport as soon as the card scrolled. `fixed`
    // keeps it against the viewport at any scroll offset.
    mountOverlay();
    const classes = [...closeEl().classList];

    expect(classes).toContain('fixed');
    expect(classes).not.toContain('absolute');
  });

  it('gives the close button an accessible name', () => {
    mountOverlay({ closeLabel: 'Close match details' });

    expect(closeEl().getAttribute('aria-label')).toBe('Close match details');
  });
});

describe('ModalOverlay — the page behind', () => {
  it('locks body scroll while open', () => {
    mountOverlay();

    expect(document.body.style.overflow).toBe('hidden');
  });

  it('restores body scroll on close', () => {
    const wrapper = mountOverlay();
    wrapper.unmount();

    expect(document.body.style.overflow).toBe('');
  });

  it('restores a pre-existing overflow rather than clearing it', () => {
    // Do not assume the page was scrollable to begin with.
    document.body.style.overflow = 'clip';
    const wrapper = mountOverlay();
    expect(document.body.style.overflow).toBe('hidden');

    wrapper.unmount();
    expect(document.body.style.overflow).toBe('clip');
  });
});

describe('ModalOverlay — dialog semantics', () => {
  it('announces itself as a modal dialog with a name', () => {
    mountOverlay({ label: 'Match details' });
    const overlay = overlayEl();

    expect(overlay.getAttribute('role')).toBe('dialog');
    expect(overlay.getAttribute('aria-modal')).toBe('true');
    expect(overlay.getAttribute('aria-label')).toBe('Match details');
  });

  it('moves focus into the dialog on open', async () => {
    const wrapper = mountOverlay();
    await wrapper.vm.$nextTick();

    expect(document.activeElement).toBe(closeEl());
  });

  it('restores focus to the opener on close', async () => {
    const opener = document.createElement('button');
    document.body.appendChild(opener);
    opener.focus();
    expect(document.activeElement).toBe(opener);

    const wrapper = mountOverlay();
    await wrapper.vm.$nextTick();
    wrapper.unmount();

    expect(document.activeElement).toBe(opener);
  });

  it('renders the slot content', () => {
    mountOverlay({}, '<p>Match details</p>');

    expect(overlayEl().textContent).toContain('Match details');
  });
});
