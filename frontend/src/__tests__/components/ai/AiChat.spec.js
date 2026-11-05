/**
 * MT AI web chat (SB-1500).
 *
 * POST /api/ai/chat is mocked at the auth store, so these cover what the
 * screen does with each reply shape: answers, follow-ups, tables, outcomes,
 * the budget and request errors — and that model output never becomes HTML.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import AiChat from '@/components/ai/AiChat.vue';

let mockAuthStore;
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mockAuthStore }));
vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://localhost:8000',
}));

const CHAT_URL = 'http://localhost:8000/api/ai/chat';

const reply = (overrides = {}) => ({
  conversation_id: 'c0ffee00-0000-4000-8000-000000000001',
  turn: 1,
  status: 'ok',
  answer: 'IFA play **NEFC** on Saturday.',
  message: null,
  outcome: 'answered',
  escalation: null,
  routed_to: [],
  tables: [],
  ...overrides,
});

const httpError = (status, detail = 'raw detail') => {
  const err = new Error(detail);
  err.status = status;
  return err;
};

const chatCalls = () =>
  mockAuthStore.apiRequest.mock.calls.filter(([url]) => url === CHAT_URL);
const sentBody = n => JSON.parse(chatCalls()[n][1].body);

const ask = async (wrapper, text) => {
  await wrapper.find('[data-testid="ai-chat-input"]').setValue(text);
  await wrapper.find('[data-testid="ai-chat-form"]').trigger('submit');
  await flushPromises();
};

describe('AiChat', () => {
  beforeEach(() => {
    mockAuthStore = { apiRequest: vi.fn(() => Promise.resolve(reply())) };
  });

  it('shows example questions when empty, and sends one when tapped', async () => {
    const wrapper = mount(AiChat);
    const chips = wrapper.findAll('[data-testid="ai-chat-example"]');
    expect(chips).toHaveLength(3);

    await chips[0].trigger('click');
    await flushPromises();

    expect(sentBody(0)).toEqual({
      message: 'When does my team play next?',
      conversation_id: null,
    });
    expect(wrapper.find('[data-testid="ai-chat-empty"]').exists()).toBe(false);
  });

  it('sends a message and shows the question and the Markdown answer', async () => {
    const wrapper = mount(AiChat);
    await ask(wrapper, '  When do IFA play?  ');

    const [url, options] = chatCalls()[0];
    expect(url).toBe(CHAT_URL);
    expect(options.method).toBe('POST');
    expect(sentBody(0)).toEqual({
      message: 'When do IFA play?',
      conversation_id: null,
    });

    expect(wrapper.find('[data-testid="ai-chat-user"]').text()).toBe(
      'When do IFA play?'
    );
    const answer = wrapper.find('[data-testid="ai-chat-answer"]');
    expect(answer.find('strong').text()).toBe('NEFC');
    expect(wrapper.find('[data-testid="ai-chat-input"]').element.value).toBe(
      ''
    );
  });

  it('disables input and shows Thinking… while waiting', async () => {
    let resolve;
    mockAuthStore.apiRequest = vi.fn(() => new Promise(r => (resolve = r)));
    const wrapper = mount(AiChat);
    await ask(wrapper, 'Hello');

    expect(wrapper.find('[data-testid="ai-chat-thinking"]').exists()).toBe(
      true
    );
    expect(
      wrapper.find('[data-testid="ai-chat-input"]').attributes('disabled')
    ).toBeDefined();
    expect(
      wrapper.find('[data-testid="ai-chat-send"]').attributes('disabled')
    ).toBeDefined();

    resolve(reply());
    await flushPromises();
    expect(wrapper.find('[data-testid="ai-chat-thinking"]').exists()).toBe(
      false
    );
  });

  it('Enter sends, Shift+Enter does not', async () => {
    const wrapper = mount(AiChat);
    const input = wrapper.find('[data-testid="ai-chat-input"]');
    await input.setValue('line one');

    await input.trigger('keydown.enter', { shiftKey: true });
    await flushPromises();
    expect(chatCalls()).toHaveLength(0);

    await input.trigger('keydown.enter');
    await flushPromises();
    expect(chatCalls()).toHaveLength(1);
  });

  it('sends the conversation_id from the first reply on a follow-up', async () => {
    const wrapper = mount(AiChat);
    await ask(wrapper, 'First');
    await ask(wrapper, 'And after that?');

    expect(sentBody(1)).toEqual({
      message: 'And after that?',
      conversation_id: 'c0ffee00-0000-4000-8000-000000000001',
    });
  });

  it('New chat clears the messages and the conversation', async () => {
    const wrapper = mount(AiChat);
    await ask(wrapper, 'First');
    await wrapper.find('[data-testid="ai-chat-new"]').trigger('click');

    expect(wrapper.findAll('[data-testid="ai-chat-user"]')).toHaveLength(0);
    expect(wrapper.find('[data-testid="ai-chat-empty"]').exists()).toBe(true);

    await ask(wrapper, 'Fresh start');
    expect(sentBody(1).conversation_id).toBeNull();
  });

  it('renders a table with highlight, numeric alignment and notes', async () => {
    mockAuthStore.apiRequest = vi.fn(() =>
      Promise.resolve(
        reply({
          answer: 'Here are the standings.',
          tables: [
            {
              title: 'U15 Homegrown Northeast',
              columns: ['#', 'Team', 'Pts', 'Form'],
              rows: [
                ['1', 'NEFC', '25', '🟩🟩🟩'],
                ['2', 'IFA', '22', '🟩🟥🟩'],
              ],
              notes: ['**IFA** have a game in hand.', 'Updated nightly.'],
              highlight: [1],
            },
          ],
        })
      )
    );
    const wrapper = mount(AiChat);
    await ask(wrapper, 'Standings?');

    const table = wrapper.find('[data-testid="ai-chat-table"]');
    expect(table.text()).toContain('U15 Homegrown Northeast');
    expect(table.findAll('th').map(th => th.text())).toEqual([
      '#',
      'Team',
      'Pts',
      'Form',
    ]);

    const rows = table.findAll('tbody tr');
    expect(rows).toHaveLength(2);
    expect(rows[0].attributes('data-highlight')).toBeUndefined();
    expect(rows[1].attributes('data-highlight')).toBe('true');
    expect(rows[1].classes()).toContain('font-bold');

    const cells = rows[0].findAll('td');
    expect(cells[2].classes()).toContain('text-right'); // Pts
    expect(cells[1].classes()).toContain('text-left'); // Team
    expect(cells[3].text()).toBe('🟩🟩🟩'); // Form stays text

    const notes = table.findAll('[data-testid="ai-chat-table-notes"] li');
    expect(notes).toHaveLength(2);
    expect(notes[0].find('strong').text()).toBe('IFA');
  });

  it('notes an escalation', async () => {
    mockAuthStore.apiRequest = vi.fn(() =>
      Promise.resolve(
        reply({
          outcome: 'escalated',
          escalation: 'data_gap',
          answer: 'Not sure.',
        })
      )
    );
    const wrapper = mount(AiChat);
    await ask(wrapper, 'Who refereed?');

    expect(wrapper.find('[data-testid="ai-chat-answer"]').text()).toBe(
      'Not sure.'
    );
    expect(wrapper.find('[data-testid="ai-chat-escalated"]').text()).toMatch(
      /follow up/
    );
  });

  it.each(['limit', 'error'])(
    'shows a %s outcome as a muted warning',
    async outcome => {
      mockAuthStore.apiRequest = vi.fn(() =>
        Promise.resolve(reply({ outcome, answer: 'I could not finish that.' }))
      );
      const wrapper = mount(AiChat);
      await ask(wrapper, 'Hard question');

      expect(wrapper.find('[data-testid="ai-chat-warning"]').text()).toBe(
        'I could not finish that.'
      );
      expect(wrapper.find('[data-testid="ai-chat-answer"]').exists()).toBe(
        false
      );
    }
  );

  it('shows the message when the budget is exhausted', async () => {
    mockAuthStore.apiRequest = vi.fn(() =>
      Promise.resolve(
        reply({
          status: 'budget_exhausted',
          answer: null,
          outcome: null,
          message: "You've used today's questions. Back tomorrow.",
        })
      )
    );
    const wrapper = mount(AiChat);
    await ask(wrapper, 'One more?');

    expect(wrapper.find('[data-testid="ai-chat-warning"]').text()).toBe(
      "You've used today's questions. Back tomorrow."
    );
  });

  it.each([
    [429, /limit/i],
    [503, /unavailable/i],
    [502, /trouble/i],
  ])(
    'on a %i shows a friendly error and keeps the typed text',
    async (status, wording) => {
      mockAuthStore.apiRequest = vi.fn(() => Promise.reject(httpError(status)));
      const wrapper = mount(AiChat);
      await ask(wrapper, 'Will this work?');

      const error = wrapper.find('[data-testid="ai-chat-error"]');
      expect(error.text()).toMatch(wording);
      expect(error.text()).not.toContain('raw detail');
      expect(wrapper.find('[data-testid="ai-chat-input"]').element.value).toBe(
        'Will this work?'
      );
      expect(wrapper.findAll('[data-testid="ai-chat-user"]')).toHaveLength(0);
    }
  );

  it('never renders model HTML (script, img onerror)', async () => {
    mockAuthStore.apiRequest = vi.fn(() =>
      Promise.resolve(
        reply({
          answer:
            '<script>window.pwned = 1</script><img src=x onerror="window.pwned = 1">',
          tables: [
            {
              title: '<img src=x onerror=alert(1)>',
              columns: ['<b>A</b>'],
              rows: [['<script>x</script>']],
              notes: ['<img src=x onerror=alert(1)>'],
              highlight: [],
            },
          ],
        })
      )
    );
    const wrapper = mount(AiChat);
    await ask(wrapper, 'xss');

    const assistant = wrapper.find('[data-testid="ai-chat-assistant"]');
    expect(assistant.find('script').exists()).toBe(false);
    expect(assistant.find('img').exists()).toBe(false);
    expect(assistant.find('th b').exists()).toBe(false);
    expect(assistant.find('[data-testid="ai-chat-answer"]').text()).toContain(
      '<script>window.pwned = 1</script>'
    );
    expect(window.pwned).toBeUndefined();
  });

  it('reopens a recent conversation and continues it', async () => {
    mockAuthStore.apiRequest = vi.fn(url => {
      if (url.endsWith('/api/ai/conversations?limit=10')) {
        return Promise.resolve({
          conversations: [{ id: 'abc', first_question: 'Old question' }],
        });
      }
      if (url.endsWith('/api/ai/conversations/abc')) {
        return Promise.resolve({
          id: 'abc',
          turns: [{ turn: 1, question: 'Old question', answer: 'Old answer' }],
        });
      }
      return Promise.resolve(reply({ conversation_id: 'abc', turn: 2 }));
    });
    const wrapper = mount(AiChat);

    await wrapper
      .find('[data-testid="ai-chat-recent-toggle"]')
      .trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="ai-chat-recent-abc"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-testid="ai-chat-user"]').text()).toBe(
      'Old question'
    );
    expect(wrapper.find('[data-testid="ai-chat-answer"]').text()).toBe(
      'Old answer'
    );

    await ask(wrapper, 'Follow-up');
    expect(sentBody(0).conversation_id).toBe('abc');
  });
});
