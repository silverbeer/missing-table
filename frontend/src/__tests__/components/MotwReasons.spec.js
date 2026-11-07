import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import MotwReasons from '@/components/MotwReasons.vue';
import MotwReasonsEditor from '@/components/MotwReasonsEditor.vue';

describe('MotwReasons (SB-1577)', () => {
  it('renders nothing for null', () => {
    const w = mount(MotwReasons, { props: { reasons: null } });
    expect(w.find('[data-testid="motw-reasons"]').exists()).toBe(false);
  });

  it('renders nothing for []', () => {
    const w = mount(MotwReasons, { props: { reasons: [] } });
    expect(w.find('[data-testid="motw-reasons"]').exists()).toBe(false);
  });

  it('marks each reason by kind, default marker for unknown', () => {
    const w = mount(MotwReasons, {
      props: {
        reasons: [
          { text: '1st vs 3rd', kind: 'standings' },
          { text: 'Three wins from three', kind: 'form' },
          { text: 'Something else', kind: 'mystery' },
        ],
      },
    });
    const items = w.findAll('[data-testid="motw-reason"]');
    expect(items.map(i => i.attributes('data-kind'))).toEqual([
      'standings',
      'form',
      'none',
    ]);
    const marks = w.findAll('[data-testid="motw-reason-mark"]');
    expect(marks.map(m => m.text())).toEqual(['📊', '🔥', '▸']);
    // Screen readers get the kind as words, not the emoji.
    expect(items[0].find('.sr-only').text()).toContain('Table');
    expect(items[2].find('.sr-only').exists()).toBe(false);
  });

  it('accepts a custom title', () => {
    const w = mount(MotwReasons, {
      props: { reasons: [{ text: 'x' }], title: 'Why this is the pick' },
    });
    expect(w.text()).toContain('Why this is the pick');
  });
});

describe('MotwReasonsEditor (SB-1577)', () => {
  const texts = w =>
    w.findAll('[data-testid="motw-reason-input"]').map(i => i.element.value);

  it('opens with one blank row when nothing was written', () => {
    const w = mount(MotwReasonsEditor, { props: { reasons: null } });
    expect(texts(w)).toEqual(['']);
  });

  it('opens with the existing reasons', () => {
    const w = mount(MotwReasonsEditor, {
      props: { reasons: [{ text: 'a', kind: 'form' }, { text: 'b' }] },
    });
    expect(texts(w)).toEqual(['a', 'b']);
    expect(w.findAll('[data-testid="motw-reason-kind"]')[0].element.value).toBe(
      'form'
    );
  });

  it('adds up to six rows and no more', async () => {
    const w = mount(MotwReasonsEditor, { props: { reasons: null } });
    const add = w.find('[data-testid="motw-reason-add"]');
    for (let i = 0; i < 8; i++) await add.trigger('click');
    expect(w.findAll('[data-testid="motw-reason-row"]')).toHaveLength(6);
    expect(add.attributes('disabled')).toBeDefined();
  });

  it('reorders and removes', async () => {
    const w = mount(MotwReasonsEditor, {
      props: { reasons: [{ text: 'a' }, { text: 'b' }, { text: 'c' }] },
    });
    await w.findAll('[data-testid="motw-reason-down"]')[0].trigger('click');
    expect(texts(w)).toEqual(['b', 'a', 'c']);
    await w.findAll('[data-testid="motw-reason-up"]')[2].trigger('click');
    expect(texts(w)).toEqual(['b', 'c', 'a']);
    await w.findAll('[data-testid="motw-reason-remove"]')[1].trigger('click');
    expect(texts(w)).toEqual(['b', 'a']);
  });

  it('saves the cleaned list', async () => {
    const w = mount(MotwReasonsEditor, { props: { reasons: null } });
    await w.find('[data-testid="motw-reason-input"]').setValue(' Unbeaten ');
    await w.find('[data-testid="motw-reason-kind"]').setValue('form');
    await w.find('[data-testid="motw-reason-add"]').trigger('click');
    await w.find('[data-testid="motw-reasons-save"]').trigger('click');
    expect(w.emitted('save')[0][0]).toEqual([
      { text: 'Unbeaten', kind: 'form' },
    ]);
  });

  it('removing every row saves [] (provided, empty)', async () => {
    const w = mount(MotwReasonsEditor, {
      props: { reasons: [{ text: 'a' }] },
    });
    await w.find('[data-testid="motw-reason-remove"]').trigger('click');
    await w.find('[data-testid="motw-reasons-save"]').trigger('click');
    expect(w.emitted('save')[0][0]).toEqual([]);
  });

  it('cancel emits cancel, not save', async () => {
    const w = mount(MotwReasonsEditor, { props: { reasons: null } });
    await w.find('[data-testid="motw-reasons-cancel"]').trigger('click');
    expect(w.emitted('cancel')).toHaveLength(1);
    expect(w.emitted('save')).toBeUndefined();
  });
});
