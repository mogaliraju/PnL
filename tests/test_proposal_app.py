"""Proposal generation in the app: commercials from the PnL engine, the job, the API.
The model is a scripted fake Bedrock client; Node builds the real Word file."""
import io
import json
import os
import unittest
from pathlib import Path

from pg_support import PgAppTestCase

from pnl import engine
from pnl.proposal_commercials import commercials_from_payload, pnl_context

SAMPLE = Path(__file__).resolve().parents[1] / 'proposals' / 'samples' / 'automatonsx'
CONTENT = json.loads((SAMPLE / 'content.json').read_text())
OPUS, SONNET = 'global.anthropic.claude-opus-4-6-v1', 'global.anthropic.claude-sonnet-4-5-20250929-v1:0'

PAYLOAD = {
    '_meta': {'id': 'crest1', 'name': 'Crestline data platform'},
    'calc_mode': 'v2',
    'project': {'customer': 'Crestline Realty', 'status': 'Draft', 'discount_pct': 5, 'duration_months': 4,
                'travel_cost': 2000, 'account_manager': 'Asha Rao'},
    'resources': [{'group': 'Data Engineering', 'role': 'Senior Data Engineer', 'level': 'L2', 'hours': 640},
                  {'group': 'Data Engineering', 'role': 'Senior Data Engineer', 'level': 'L2', 'hours': 640},
                  {'group': 'Reporting', 'role': 'Power BI Developer', 'level': 'L1', 'hours': 320}],
    'rate_card': [{'level': 'L1', 'rates': {'Data Engineering': 20, 'Reporting': 18}},
                  {'level': 'L2', 'rates': {'Data Engineering': 30, 'Reporting': 26}}],
    'one_time_costs': [{'label': 'Fabric F64 capacity', 'amount': 15600, 'category': 'license', 'exclude_from_margin': True},
                       {'label': 'Accelerator licence', 'amount': 3000, 'category': 'one_time'}],
    'cloud4c_margin': 0.30, 'ax_margin': 0.15, 'fx_rate': 90,
}
INTAKE = json.loads((SAMPLE / 'intake.json').read_text())


class TestCommercials(unittest.TestCase):
    def test_lines_add_up_to_the_engine_contract_value(self):
        com = commercials_from_payload(PAYLOAD, 'automatonsx', project_name='Crestline Realty', version_no=2)
        cv = engine.calculate(PAYLOAD).contract_value
        self.assertEqual(sum(i['amount'] for i in com['otc_items']), round(float(cv)))
        names = [i['component'] for i in com['otc_items']]
        self.assertEqual(names, ['Data Engineering', 'Reporting', 'Fabric F64 capacity', 'Accelerator licence',
                                 'Travel and expenses'])
        lic = next(i for i in com['otc_items'] if i['component'] == 'Fabric F64 capacity')
        self.assertEqual((lic['amount'], lic['cost_type']), (15600, 'License'))      # passed through at cost

    def test_duration_and_team_come_from_the_plan(self):
        com = commercials_from_payload(PAYLOAD, 'cloud4c', project_name='X', version_no=1)
        self.assertEqual(com['duration_weeks'], 17)                                  # 4 months
        self.assertIn({'role': 'Senior Data Engineer', 'count': 2, 'allocation': '90%'}, com['team'])
        self.assertEqual([p['percent'] for p in com['payment_plan']], [20, 20, 40, 20])

    def test_model_context_has_no_amounts(self):
        ctx = pnl_context(commercials_from_payload(PAYLOAD, 'cloud4c', project_name='X', version_no=1))
        self.assertEqual(set(ctx), {'duration_weeks', 'team'})


class TestChecks(unittest.TestCase):
    def setUp(self):
        self.com = commercials_from_payload(PAYLOAD, 'automatonsx', project_name='Crestline Realty', version_no=1)

    def ids_failing(self, intake, content):
        from pnl.proposal_checks import run_checks
        return {c['id'] for c in run_checks(intake, content, self.com) if not c['ok']}

    def test_sample_passes(self):
        self.assertEqual(self.ids_failing(INTAKE, CONTENT), set())

    def test_problems_are_caught(self):
        bad = json.loads(json.dumps(CONTENT))
        bad['executive_summary'][0] = 'CUSTOMER runs Yardi. Cloud4C will deliver it for $50,000 \u2014 fast.'
        bad['timeline']['stages'][-1]['timeline'] = 'Weeks 18 to 24'
        bad.pop('risks')
        bad['inventory'] = {'rows': [{'object_type': 'Pipelines', 'count': '999'}]}
        self.assertEqual(self.ids_failing(INTAKE, bad),
                         {'no_prices', 'timeline', 'placeholders', 'brand', 'sections', 'inventory', 'style'})

    def test_commercials_mismatch_is_caught(self):
        from pnl.proposal_checks import run_checks
        com = {**self.com, 'otc_items': self.com['otc_items'][:-1]}
        self.assertFalse(next(c for c in run_checks(INTAKE, CONTENT, com) if c['id'] == 'commercials')['ok'])


class FakeBedrock:
    def __init__(self, *replies, fail=()):
        self.replies, self.fail, self.calls = list(replies), set(fail), []

    def converse(self, **kw):
        self.calls.append(kw)
        if kw['modelId'] in self.fail:
            raise RuntimeError('AccessDeniedException: no access')
        content = self.replies.pop(0) if self.replies else CONTENT
        return {'output': {'message': {'role': 'assistant', 'content': [
                    {'toolUse': {'toolUseId': f't{len(self.calls)}', 'name': 'submit_proposal_content', 'input': content}}]}},
                'stopReason': 'tool_use', 'usage': {'inputTokens': 9000, 'outputTokens': 4000}}


class ProposalCase(PgAppTestCase):
    def setUp(self):
        super().setUp()
        self.auth()
        os.environ['PNL_PROPOSALS_INLINE'] = '1'
        self.storage.save_project_record('crest1', PAYLOAD)
        self.storage.save_project_version('crest1', 'v1', PAYLOAD)
        from proposals import generator
        self.generator = generator

    def tearDown(self):
        self.generator.set_client(None)
        os.environ.pop('PNL_PROPOSALS_INLINE', None)
        super().tearDown()

    def generate(self, fake, intake=None, version=1):
        self.generator.set_client(fake)
        return self.client.post(f'/api/projects/crest1/versions/{version}/proposals', json=intake or INTAKE)


class TestProposalJob(ProposalCase):
    def test_generates_a_word_file_priced_from_the_pnl(self):
        fake = FakeBedrock()
        r = self.generate(fake)
        self.assertEqual(r.status_code, 202, r.data)
        pid = r.get_json()['proposal_id']
        p = self.client.get(f'/api/proposals/{pid}?content=1').get_json()
        self.assertEqual(p['status'], 'ready', p.get('error'))
        self.assertEqual(p['model_id'], OPUS)
        self.assertEqual(p['open_questions'], CONTENT['open_questions'])
        self.assertEqual(sum(i['amount'] for i in p['commercials']['otc_items']),
                         round(float(engine.calculate(PAYLOAD).contract_value)))
        d = self.client.get(f'/api/proposals/{pid}/download')
        self.assertEqual(d.status_code, 200)
        self.assertTrue(d.data.startswith(b'PK'))
        self.assertGreater(len(d.data), 50_000)
        # the model saw the plan's duration and team, never an amount
        sent = fake.calls[0]['messages'][0]['content'][0]['text']
        self.assertIn('"duration_weeks": 17', sent)
        for amount in [str(i['amount']) for i in p['commercials']['otc_items']] + ['15600']:
            self.assertNotIn(amount, sent)
        self.assertNotIn('Srikar', sent)                      # people stay out of the prompt
        self.assertTrue(p['checks'] and all(c['ok'] for c in p['checks']), p['checks'])
        listed = self.client.get('/api/projects/crest1/proposals').get_json()['proposals']
        self.assertEqual([x['id'] for x in listed], [pid])

    def test_falls_back_to_sonnet(self):
        r = self.generate(FakeBedrock(fail={OPUS}))
        p = self.client.get(f"/api/proposals/{r.get_json()['proposal_id']}").get_json()
        self.assertEqual((p['status'], p['model_id']), ('ready', SONNET))

    def test_invalid_content_is_retried_then_fails_readably(self):
        bad = {**CONTENT, 'objectives': []}
        fake = FakeBedrock(bad, bad)
        r = self.generate(fake)
        p = self.client.get(f"/api/proposals/{r.get_json()['proposal_id']}").get_json()
        self.assertEqual(p['status'], 'failed')
        self.assertIn('objectives', p['error'])
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(fake.calls[1]['messages'][-1]['content'][0]['toolResult']['status'], 'error')
        self.assertEqual(self.client.get(f"/api/proposals/{p['id']}/download").status_code, 404)

    def test_access_denied_everywhere(self):
        r = self.generate(FakeBedrock(fail={OPUS, SONNET}))
        p = self.client.get(f"/api/proposals/{r.get_json()['proposal_id']}").get_json()
        self.assertEqual(p['status'], 'failed')
        self.assertIn('Bedrock', p['error'])

    def test_input_is_checked(self):
        r = self.generate(FakeBedrock(), {**INTAKE, 'brand': ''})
        self.assertEqual(r.status_code, 400)
        self.assertIn('AutomatonsX or Cloud4C', r.get_json()['error'])
        self.assertEqual(self.generate(FakeBedrock(), version=7).status_code, 400)
        mig = {**INTAKE, 'engagement_type': 'migration', 'migration': {}}
        self.assertIn('source and target', self.generate(FakeBedrock(), mig).get_json()['error'])
        self.assertIn('brief', self.generate(FakeBedrock(), {**INTAKE, 'brief': ''}).get_json()['error'])

    def test_brief_can_come_from_an_uploaded_word_file(self):
        import docx
        d = docx.Document()
        d.add_paragraph('Crestline needs Yardi and Oracle EBS in Fabric.')
        buf = io.BytesIO()
        d.save(buf)
        self.generator.set_client(FakeBedrock())
        r = self.client.post('/api/projects/crest1/versions/1/proposals', content_type='multipart/form-data',
                             data={'intake': json.dumps({**INTAKE, 'brief': ''}),
                                   'document': (io.BytesIO(buf.getvalue()), 'brd.docx')})
        self.assertEqual(r.status_code, 202, r.data)
        intake = json.loads(self.q("SELECT intake FROM proposal").fetchone()['intake'])
        self.assertIn('Yardi and Oracle EBS', intake['document_text'])
        bad = self.client.post('/api/projects/crest1/versions/1/proposals', content_type='multipart/form-data',
                               data={'intake': json.dumps(INTAKE), 'document': (io.BytesIO(b'x'), 'brd.exe')})
        self.assertEqual(bad.status_code, 400)

    def test_rate_limit_and_stuck_jobs(self):
        for _ in range(10):
            self.q("INSERT INTO proposal(project_id, version_id, version_no, brand, engagement_type, intake, created_by, status) "
                   "VALUES ('crest1','v1',1,'cloud4c','greenfield','{}','admin','running')")
        self.assertIn('10 proposals an hour', self.generate(FakeBedrock()).get_json()['error'])
        self.q("INSERT INTO proposal(project_id, version_id, version_no, brand, engagement_type, intake, created_by, status, created_at) "
               "VALUES ('crest1','v1',1,'cloud4c','greenfield','{}','x','running', now() - interval '1 hour')")
        rows = self.client.get('/api/projects/crest1/proposals').get_json()['proposals']
        self.assertEqual(sum(1 for x in rows if x['status'] == 'failed'), 1)

    def test_capabilities_are_admin_only(self):
        self.assertEqual(self.client.get('/api/proposals/capabilities').status_code, 200)
        self.auth('viewer')
        self.assertEqual(self.client.get('/api/proposals/capabilities').status_code, 403)
