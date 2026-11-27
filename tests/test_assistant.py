"""Phase 8: PnL assistant (Claude Opus 4.6, then Sonnet 4.5 and GPT OSS 120B as fallbacks, on Bedrock Converse) with a scripted fake model client."""
import contextlib
import json
import os
from unittest.mock import patch

from pg_support import PgAppTestCase

PAYLOAD = {
    '_meta': {'id': 'acme1', 'name': 'ACME data platform'},
    'project': {'customer': 'ACME Corp', 'status': 'Draft', 'stage': 'Proposal', 'discount_pct': 0},
    'resources': [{'group': 'Data', 'role': 'Data engineer', 'level': 'L2', 'hours': 1000}],
    'rate_card': [{'level': 'L2', 'rates': {'Data': 30}}],
    'cloud4c_margin': 0.40, 'ax_margin': 0.10, 'fx_rate': 90,
}


def tool_call(name, args, tid='t1'):
    return [{'messageStart': {'role': 'assistant'}},
            {'contentBlockStart': {'start': {'toolUse': {'toolUseId': tid, 'name': name}}, 'contentBlockIndex': 0}},
            {'contentBlockDelta': {'delta': {'toolUse': {'input': json.dumps(args)}}, 'contentBlockIndex': 0}},
            {'contentBlockStop': {'contentBlockIndex': 0}},
            {'messageStop': {'stopReason': 'tool_use'}},
            {'metadata': {'usage': {'inputTokens': 100, 'outputTokens': 20}}}]


def answer(text):
    return [{'messageStart': {'role': 'assistant'}},
            {'contentBlockDelta': {'delta': {'reasoningContent': {'text': 'private'}}, 'contentBlockIndex': 0}},
            {'contentBlockDelta': {'delta': {'text': text[:5]}, 'contentBlockIndex': 1}},
            {'contentBlockDelta': {'delta': {'text': text[5:]}, 'contentBlockIndex': 1}},
            {'contentBlockStop': {'contentBlockIndex': 1}},
            {'messageStop': {'stopReason': 'end_turn'}},
            {'metadata': {'usage': {'inputTokens': 150, 'outputTokens': 30}}}]


class FakeBedrock:
    def __init__(self, *turns):
        self.turns, self.calls = list(turns), []

    def converse_stream(self, **kw):
        self.calls.append(json.loads(json.dumps(kw, default=str)))
        turn = self.turns.pop(0) if self.turns else answer('Done.')
        return {'stream': iter(turn)}


class FailingModel(FakeBedrock):
    """Raises for the listed model ids (optionally after some output), answers for the others."""
    def __init__(self, down, *turns, after=None):
        super().__init__(*turns)
        self.down, self.after = set(down), after

    def converse_stream(self, **kw):
        if kw['modelId'] in self.down:
            self.calls.append({'modelId': kw['modelId'], 'failed': True})
            if self.after is None:
                raise RuntimeError('AccessDeniedException: model access not granted')
            def broken():
                yield from self.after
                raise RuntimeError('stream dropped')
            return {'stream': broken()}
        return super().converse_stream(**kw)


class AssistantCase(PgAppTestCase):
    def setUp(self):
        super().setUp()
        self.auth()
        os.environ['PNL_ASSISTANT_FAKE'] = '1'
        self.storage.save_project_record('acme1', PAYLOAD)
        self.storage.save_project_version('acme1', 'v1', PAYLOAD)
        from pnl.assistant import agent, tools
        self.agent, self.tools = agent, tools
        conn = self.conn

        @contextlib.contextmanager
        def shared_ro():
            yield conn
        self._ro = patch.object(tools, '_ro', shared_ro)
        self._ro.start()

    def tearDown(self):
        self._ro.stop()
        self.agent.set_client(None)
        self.agent._down_until.clear()
        os.environ.pop('PNL_ASSISTANT_FAKE', None)
        super().tearDown()

    def ask(self, fake, message, **extra):
        self.agent.set_client(fake)
        r = self.client.post('/api/assistant/chat', json={'message': message, **extra})
        self.assertEqual(r.status_code, 200, r.data)
        return [json.loads(line[6:]) for line in r.data.decode().split('\n\n') if line.startswith('data: ')]


class TestAssistant(AssistantCase):
    def test_tool_round_trip(self):
        fake = FakeBedrock(tool_call('search_projects', {'query': 'acme'}), answer('ACME Corp is at 10.0% AX.'))
        ev = self.ask(fake, 'How is ACME doing?')
        kinds = [e['type'] for e in ev]
        self.assertEqual(kinds[0], 'session')
        self.assertIn({'type': 'tool', 'name': 'search_projects', 'status': 'done'}, ev)
        self.assertEqual(''.join(e['text'] for e in ev if e['type'] == 'text'), 'ACME Corp is at 10.0% AX.')
        self.assertEqual(kinds[-1], 'done')
        self.assertIn('sources', kinds)
        # the model got the tool result as JSON with engine figures
        result = fake.calls[1]['messages'][-1]['content'][0]['toolResult']
        self.assertEqual(result['status'], 'success')
        proj = result['content'][0]['json']['projects'][0]
        self.assertEqual(proj['project_id'], 'acme1')
        self.assertEqual(proj['contract_value_usd'], 60000.0)          # 30000 / (1 - 0.5)
        # reasoning is never shown or stored
        self.assertNotIn('private', json.dumps(ev))
        hist = self.client.get('/api/assistant/session').get_json()['messages']
        self.assertEqual([m['role'] for m in hist], ['user', 'assistant'])
        calls = self.q("SELECT tool, ok FROM assistant_tool_call").fetchall()
        self.assertEqual([(c['tool'], c['ok']) for c in calls], [('search_projects', True)])

    OPUS, SONNET, GPT = ('global.anthropic.claude-opus-4-6-v1', 'global.anthropic.claude-sonnet-4-5-20250929-v1:0',
                         'openai.gpt-oss-120b-1:0')

    def test_main_model_is_opus_then_sonnet_then_gpt(self):
        fake = FakeBedrock(answer('Hello there.'))
        self.ask(fake, 'Hi')
        self.assertEqual(fake.calls[0]['modelId'], self.OPUS)
        self.assertEqual(self.agent.models_to_try(), [self.OPUS, self.SONNET, self.GPT])

    def test_falls_back_when_main_model_fails(self):
        fake = FailingModel({self.OPUS}, tool_call('search_projects', {'query': 'acme'}), answer('ACME is fine.'))
        ev = self.ask(fake, 'How is ACME?')
        self.assertNotIn('error', [e['type'] for e in ev])
        self.assertEqual(''.join(e['text'] for e in ev if e['type'] == 'text'), 'ACME is fine.')
        self.assertEqual([c['modelId'] for c in fake.calls], [self.OPUS, self.SONNET, self.SONNET])  # later rounds stay put
        # for the next few minutes Opus goes to the back of the line
        fake2 = FailingModel({self.OPUS}, answer('Again.'))
        self.ask(fake2, 'Again?')
        self.assertEqual([c['modelId'] for c in fake2.calls], [self.SONNET])
        self.assertEqual(self.agent.models_to_try(), [self.SONNET, self.GPT, self.OPUS])

    def test_both_claude_models_down_uses_gpt(self):
        fake = FailingModel({self.OPUS, self.SONNET}, answer('From GPT.'))
        ev = self.ask(fake, 'Hi')
        self.assertEqual([c['modelId'] for c in fake.calls], [self.OPUS, self.SONNET, self.GPT])
        self.assertEqual(''.join(e['text'] for e in ev if e['type'] == 'text'), 'From GPT.')

    def test_no_switch_after_output_started(self):
        fake = FailingModel({self.OPUS}, after=[{'messageStart': {'role': 'assistant'}},
                                               {'contentBlockDelta': {'delta': {'text': 'Half an'}, 'contentBlockIndex': 0}}])
        ev = self.ask(fake, 'Hi')
        self.assertEqual([c['modelId'] for c in fake.calls], [self.OPUS])
        self.assertIn('error', [e['type'] for e in ev])

    def test_all_models_down(self):
        fake = FailingModel({self.OPUS, self.SONNET, self.GPT})
        ev = self.ask(fake, 'Hi')
        self.assertEqual(len(fake.calls), 3)
        self.assertIn('reference', [e for e in ev if e['type'] == 'error'][0]['message'])

    def test_fallback_list_from_environment(self):
        with patch.dict(os.environ, {'BEDROCK_FALLBACK_MODEL_ID': 'none'}):
            fake = FailingModel({self.OPUS})
            self.ask(fake, 'Hi')
            self.assertEqual(len(fake.calls), 1)
        with patch.dict(os.environ, {'BEDROCK_FALLBACK_MODEL_ID': f' {self.GPT} , {self.OPUS},{self.GPT}'}):
            self.assertEqual(self.agent.models_to_try(), [self.OPUS, self.GPT])

    def test_follow_up_sends_earlier_turns(self):
        self.ask(FakeBedrock(answer('First answer.')), 'First question')
        fake = FakeBedrock(answer('Second answer.'))
        self.ask(fake, 'Second question')
        msgs = fake.calls[0]['messages']
        self.assertEqual([m['role'] for m in msgs], ['user', 'assistant', 'user'])
        self.assertEqual(msgs[1]['content'][0]['text'], 'First answer.')

    def test_scenario_is_not_saved(self):
        before = self.q("SELECT payload FROM projects WHERE pid='acme1'").fetchone()['payload']
        fake = FakeBedrock(tool_call('calculate_scenario', {'project': 'ACME', 'overrides': {'ax_pct': 20, 'discount_pct': 5}}),
                           answer('With 20% AX the contract value is higher.'))
        ev = self.ask(fake, 'What if ACME AX is 20%?')
        scen = [e for e in ev if e['type'] == 'scenario'][0]
        self.assertEqual(scen['project_id'], 'acme1')
        self.assertEqual(scen['overrides'], {'ax_pct': 20, 'discount_pct': 5})
        out = fake.calls[1]['messages'][-1]['content'][0]['toolResult']['content'][0]['json']
        self.assertFalse(out['saved'])
        self.assertGreater(out['after']['list_price'], out['before']['list_price'])
        self.assertEqual(self.q("SELECT payload FROM projects WHERE pid='acme1'").fetchone()['payload'], before)

    def test_export_link(self):
        fake = FakeBedrock(tool_call('export_pnl_excel', {'project': 'acme1', 'version': 1}), answer('Here it is.'))
        ev = self.ask(fake, 'Download the ACME PnL')
        f = [e for e in ev if e['type'] == 'file'][0]
        self.assertEqual(f['filename'], 'ACME Corp PnL v1.xlsx')
        r = self.client.get(f['url'])
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b'PK'))
        self.auth('viewer')
        self.assertEqual(self.client.get(f['url']).status_code, 404)          # only the person who asked
        self.auth('admin')
        self.q("UPDATE export_token SET expires_at = now() - interval '1 minute'")
        self.assertEqual(self.client.get(f['url']).status_code, 410)

    def test_bad_tool_input_is_rejected_not_run(self):
        fake = FakeBedrock(tool_call('get_project', {'project': 'acme1', 'drop_table': True}), answer('Sorry.'))
        self.ask(fake, 'Show ACME')
        res = fake.calls[1]['messages'][-1]['content'][0]['toolResult']
        self.assertEqual(res['status'], 'error')
        self.assertIn('unknown fields', res['content'][0]['text'])
        self.assertFalse(self.q("SELECT ok FROM assistant_tool_call").fetchone()['ok'])

    def test_ambiguous_project_asks(self):
        self.storage.save_project_record('acme2', {**PAYLOAD, '_meta': {'id': 'acme2', 'name': 'ACME phase 2'}})
        fake = FakeBedrock(tool_call('get_project', {'project': 'ACME'}), answer('Which one?'))
        self.ask(fake, 'Show ACME')
        text = fake.calls[1]['messages'][-1]['content'][0]['toolResult']['content'][0]['text']
        self.assertIn('Several projects match', text)

    def test_round_limit(self):
        fake = FakeBedrock(*[tool_call('list_versions', {'project': 'acme1'}, f't{i}') for i in range(10)])
        ev = self.ask(fake, 'Loop')
        self.assertEqual(len(fake.calls), self.agent.MAX_ROUNDS)
        self.assertTrue(any(e['type'] == 'error' and 'too many steps' in e['message'] for e in ev))

    def test_rate_limit(self):
        sid = self.agent.new_session('admin')
        for _ in range(self.agent.RATE_LIMIT[0]):
            self.q("INSERT INTO assistant_message(session_id, role, content) VALUES (%s, 'user', '[]')", (sid,))
        self.agent.set_client(FakeBedrock())
        self.assertEqual(self.client.post('/api/assistant/chat', json={'message': 'hi'}).status_code, 429)

    def test_not_configured(self):
        os.environ.pop('PNL_ASSISTANT_FAKE', None)
        with patch.dict(os.environ, {}, clear=False):
            for k in ('AWS_BEARER_TOKEN_BEDROCK', 'AWS_ACCESS_KEY_ID', 'AWS_PROFILE'):
                os.environ.pop(k, None)
            self.agent.set_client(None)
            s = self.client.get('/api/assistant/session').get_json()
            self.assertFalse(s['available'])
            self.assertIn('AWS_BEARER_TOKEN_BEDROCK', s['reason'])
            self.assertEqual(self.client.post('/api/assistant/chat', json={'message': 'hi'}).status_code, 503)

    def test_tool_definitions_are_converse_shape(self):
        cfg = self.tools.tool_config()
        names = {t['toolSpec']['name'] for t in cfg['tools']}
        self.assertEqual(len(names), 9)
        for t in cfg['tools']:
            self.assertFalse(t['toolSpec']['inputSchema']['json']['additionalProperties'])


class TestReadOnlyTools(PgAppTestCase):
    def test_tool_connection_cannot_write(self):
        from pnl.assistant import tools
        with tools._ro() as conn:                      # the real read-only connection
            with self.assertRaises(Exception) as cm:
                conn.execute("UPDATE projects SET name = 'x'")
        self.assertIn('read-only', str(cm.exception))


class TestDemoMode(PgAppTestCase):
    def test_demo_client_never_in_production(self):
        from pnl import config
        from pnl.assistant import agent
        agent.set_client(None)
        os.environ['PNL_ASSISTANT_FAKE'] = '1'
        try:
            config.IS_PRODUCTION = True
            for k in ('AWS_BEARER_TOKEN_BEDROCK', 'AWS_ACCESS_KEY_ID', 'AWS_PROFILE'):
                os.environ.pop(k, None)
            client = agent.get_client() if agent.configured() else None
            self.assertNotIsInstance(client, agent.DemoClient)
        finally:
            config.IS_PRODUCTION = False
            os.environ.pop('PNL_ASSISTANT_FAKE', None)
            agent.set_client(None)
