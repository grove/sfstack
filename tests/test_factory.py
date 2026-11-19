"""Regression tests for consequential evidence and permission decisions."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from common import (MAX_FILE_BYTES, contracts, inspect_artifact, load_json, now,
                    read_regular, workflow_errors)
from factory import evaluate_gate, plan

AT = now('2026-11-19T12:00:00Z')


class FactoryChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT.parent)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.examples = self.base / 'examples'
        shutil.copytree(ROOT / 'examples', self.examples)

    def edit(self, relative, callback):
        path = self.examples / relative
        data = load_json(path)
        callback(data)
        path.write_text(json.dumps(data))

    def gate(self, request='gate-request.json', at=AT):
        return evaluate_gate(self.examples / request, self.examples / 'policy.json', at)

    def assertBlocked(self, phrase=None):
        result = self.gate()
        self.assertEqual('blocked', result['decision'], result)
        if phrase:
            self.assertIn(phrase, ' '.join(result['reasons']))

    def test_complete_evidence_and_exact_grant_allow_reference_gate(self):
        self.assertEqual('allowed', self.gate()['decision'])

    def test_missing_grant_blocks(self):
        self.edit('policy.json', lambda p: p.update(grants=[]))
        self.assertBlocked('authorization')

    def test_expired_grant_blocks(self):
        self.assertEqual('blocked', self.gate(at=now('2026-11-19T13:00:00Z'))['decision'])

    def test_scope_and_run_cannot_borrow_authority(self):
        for field, value in [('scope', 'repository:other/change:42'), ('run_id', 'other-run')]:
            with self.subTest(field=field):
                original = (self.examples / 'gate-request.json').read_text()
                self.edit('gate-request.json', lambda p: p.update({field: value}))
                self.assertBlocked('authorization')
                (self.examples / 'gate-request.json').write_text(original)

    def test_absent_policy_rule_is_not_an_empty_rule(self):
        self.edit('policy.json', lambda p: p['required_artifacts'].pop('integration.modify'))
        self.assertBlocked('no explicit evidence rule')

    def test_missing_required_proof_blocks(self):
        self.edit('gate-request.json', lambda p: p['artifacts'].remove('records/review-report.json'))
        self.assertBlocked('Missing required review-report')

    def test_revision_inputs_and_environment_invalidate_evidence(self):
        for field, value in [('revision','other'), ('input_digest','0'*64), ('environment','other')]:
            with self.subTest(field=field):
                original = (self.examples / 'records/verification-report.json').read_text()
                self.edit('records/verification-report.json', lambda p: p['subject'].update({field:value}))
                self.assertBlocked('stale subject')
                (self.examples / 'records/verification-report.json').write_text(original)

    def test_modified_evidence_bytes_block(self):
        (self.examples / 'records/evidence/fixture.txt').write_text('Changed after observation.')
        self.assertBlocked('digest mismatch')

    def test_zero_boolean_failed_and_skipped_verification_block(self):
        cases = [dict(executed_count=0), dict(executed_count=True), dict(failed_count=1),
                 dict(skipped_required=['integration-check']), dict(required_count=2)]
        for change in cases:
            with self.subTest(change=change):
                original = (self.examples / 'records/verification-report.json').read_text()
                self.edit('records/verification-report.json', lambda p: p['payload'].update(change))
                self.assertBlocked()
                (self.examples / 'records/verification-report.json').write_text(original)

    def test_no_execution_evidence_cannot_verify(self):
        self.edit('records/verification-report.json', lambda p: p['evidence'][0].update(kind='analysis'))
        self.assertBlocked('execution evidence')

    def test_missing_evidence_reference_blocks(self):
        self.edit('records/verification-report.json', lambda p: p['checks'][0].update(evidence=['missing']))
        self.assertBlocked('evidence references')

    def test_open_blocker_overrides_pass_label(self):
        self.edit('records/review-report.json', lambda p: p['payload'].update(findings=[
            {'id':'r-1','blocking':True,'disposition':'open','severity':'critical'}]))
        self.assertBlocked('unresolved blocking')

    def test_resolved_finding_can_pass(self):
        self.edit('records/review-report.json', lambda p: p['payload'].update(findings=[
            {'id':'r-1','blocking':True,'disposition':'resolved'}]))
        self.assertEqual('allowed', self.gate()['decision'])

    def test_malformed_review_details_block_instead_of_crashing(self):
        for finding in [{'blocking':True,'disposition':[]},
                        {'blocking':True,'disposition':'accepted-risk','waiver':{'evidence':[]}}]:
            with self.subTest(finding=finding):
                self.edit('records/review-report.json', lambda p:p['payload'].update(findings=[finding]))
                self.assertBlocked()

    def test_risk_acceptance_requires_recorded_approval_evidence(self):
        self.edit('records/review-report.json', lambda p: p['payload'].update(findings=[
            {'id':'r-1','blocking':True,'disposition':'accepted-risk'}]))
        self.assertBlocked('unresolved blocking')
        def add_approval(p):
            approval = deepcopy(p['evidence'][0])
            approval.update(id='waiver-1',kind='approval')
            p['evidence'].append(approval)
            p['payload']['findings'][0]['waiver'] = {'actor':'demo-owner','decision':'Accept this bounded demo risk.','evidence':'waiver-1'}
        self.edit('records/review-report.json', add_approval)
        self.assertEqual('allowed', self.gate()['decision'])

    def test_unknown_numeric_and_same_reviewer_identities_block(self):
        cases=[{'reviewer':1,'change_author':2,'independence_basis':True},
               {'reviewer':'unknown'}, {'reviewer':'demo-builder'}, {'reviewer':'demo-builder '}]
        for change in cases:
            with self.subTest(change=change):
                original=(self.examples/'records/review-report.json').read_text()
                self.edit('records/review-report.json',lambda p:p['payload'].update(change))
                self.assertBlocked('independently identified')
                (self.examples/'records/review-report.json').write_text(original)

    def test_waiting_review_assessment_is_not_integration_readiness(self):
        self.edit('records/review-status.json', lambda p: p['payload'].update(readiness='waiting'))
        self.assertBlocked('readiness')

    def test_review_status_tracks_current_head_and_required_checks(self):
        self.edit('records/review-status.json', lambda p: p['payload'].update(head='old', checks=[{'id':'ci','status':'pending'}]))
        self.assertBlocked('required check')

    def test_duplicate_type_and_identity_cannot_hide_conflicting_report(self):
        source = self.examples / 'records/review-report.json'
        other = load_json(source)
        other['payload']['reviewer'] = 'another-reviewer'
        (self.examples / 'records/duplicate.json').write_text(json.dumps(other))
        self.edit('gate-request.json', lambda p: p['artifacts'].append('records/duplicate.json'))
        self.assertBlocked('Duplicate artifact identity')

    def test_future_and_expired_observations_block(self):
        for created in ('2026-11-19T12:01:00Z','2026-11-19T10:00:00Z'):
            with self.subTest(created=created):
                self.edit('records/review-report.json', lambda p: p.update(created_at=created))
                self.assertBlocked()

    def test_artifact_escape_is_rejected_before_read(self):
        self.edit('gate-request.json', lambda p: p['artifacts'].append('../outside.json'))
        with self.assertRaisesRegex(ValueError,'escapes'):
            self.gate()

    def test_external_evidence_is_unverifiable_offline(self):
        self.edit('records/review-report.json', lambda p: p['evidence'][0].update(uri='https://example.invalid/log'))
        self.assertBlocked('relative local path')

    @unittest.skipUnless(hasattr(os, 'symlink'), 'Symlinks not supported')
    def test_symlink_escape_blocks_evidence(self):
        outside = self.base / 'outside.txt'
        outside.write_text('outside')
        (self.examples / 'records/evidence/escape.txt').symlink_to(outside)
        self.edit('records/review-report.json', lambda p: p['evidence'][0].update(uri='evidence/escape.txt'))
        self.assertBlocked('escapes')

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'FIFO not supported')
    def test_nonregular_files_are_rejected_without_waiting(self):
        fifo = self.base / 'pipe'
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            load_json(fifo)

    def test_oversized_input_is_rejected(self):
        path = self.base / 'large'
        with path.open('wb') as stream:
            stream.truncate(MAX_FILE_BYTES + 1)
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            read_regular(path)

    def test_duplicate_json_keys_are_not_silently_overwritten(self):
        path = self.base / 'duplicate.json'
        path.write_text('{"status":"failed","status":"passed"}')
        with self.assertRaisesRegex(ValueError,'Duplicate JSON key'):
            load_json(path)

    def test_initial_plan_selects_only_available_frontier(self):
        result = plan(ROOT / 'workflows/feature.json', self.examples / 'feature-run.json', AT)
        self.assertEqual(['orient'], result['ready'])
        self.assertEqual([], result['completed'])

    def test_completed_orientation_unblocks_clarification(self):
        self.edit('feature-run.json', lambda p: p['completed'].update(orient=['records/project-context.json']))
        result = plan(ROOT / 'workflows/feature.json', self.examples / 'feature-run.json', AT)
        self.assertEqual(['clarify'], result['ready'])
        self.assertEqual(['orient'], result['completed'])

    def test_completed_artifact_with_wrong_producer_cannot_unlock_successors(self):
        self.edit('feature-run.json', lambda p: p['completed'].update(orient=['records/project-context.json']))
        self.edit('records/project-context.json', lambda p: p['producer'].update(skill='wrong-skill'))
        result = plan(ROOT / 'workflows/feature.json', self.examples / 'feature-run.json', AT)
        self.assertEqual('blocked', result['status'])
        self.assertIn('producer mismatch', ' '.join(result['blocked']['orient']))

    def test_missing_capability_is_blocked_without_substitution(self):
        self.edit('feature-run.json', lambda p: p.update(capabilities=['artifact.write']))
        result = plan(ROOT / 'workflows/feature.json', self.examples / 'feature-run.json', AT)
        self.assertEqual('blocked', result['status'])
        self.assertIn('workspace.read', ' '.join(result['blocked']['orient']))

    def test_workflow_cycle_missing_binding_and_orphan_are_invalid(self):
        catalog = contracts()
        original = load_json(ROOT / 'workflows/feature.json')
        changed = deepcopy(original)
        changed['steps'][0]['needs'] = [changed['steps'][-1]['id']]
        self.assertIn('cycle', ' '.join(workflow_errors(changed,catalog)))
        changed = deepcopy(original)
        changed['steps'][0]['bindings'] = {}
        self.assertIn('missing required', ' '.join(workflow_errors(changed,catalog)))
        changed = deepcopy(original)
        changed['steps'].append({'id':'orphan','skill':'sf-clarify-outcome','needs':[],'bindings':{'request':'input:request'}})
        self.assertIn('omits terminal', ' '.join(workflow_errors(changed,catalog)))

    def test_specialist_assessment_can_bind_into_review(self):
        workflow = load_json(ROOT / 'workflows/feature.json')
        workflow['steps'].append({'id':'security','skill':'sf-assess-security','needs':['orient','build'],
            'bindings':{'project-context':'step:orient:project-context','change-set':'step:build:change-set'}})
        review = next(step for step in workflow['steps'] if step['id'] == 'review')
        review['needs'].append('security')
        review['bindings']['security-assessment'] = 'step:security:security-assessment'
        self.assertEqual([], workflow_errors(workflow, contracts()))

    def test_bounded_recipe_does_not_complete_a_multi_item_plan_as_one_change(self):
        workflow = {'schema_version':'1.0','id':'single-build','summary':'One increment only.',
            'inputs':['work-plan','specification'], 'completion':['build'],
            'steps':[{'id':'build','skill':'sf-build-change','needs':[], 'max_work_items':1,
                'bindings':{'work-plan':'input:work-plan','specification':'input:specification'}}]}
        workflow_path = self.base / 'single-build.json'
        workflow_path.write_text(json.dumps(workflow))
        work_plan = load_json(self.examples / 'records/specification.json')
        work_plan.update(artifact_id='demo-work-plan', artifact_type='work-plan')
        work_plan['payload'] = {'items':[{'id':'one'},{'id':'two'}],'ready_frontier':['one','two']}
        work_path = self.examples / 'records/work-plan.json'
        work_path.write_text(json.dumps(work_plan))
        self.edit('feature-run.json', lambda p: p.update(inputs={'specification':'records/specification.json','work-plan':'records/work-plan.json'}))
        result = plan(workflow_path,self.examples/'feature-run.json',AT)
        self.assertEqual('blocked',result['status'])
        self.assertIn('selected increment',' '.join(result['blocked']['build']))
        work_plan['payload'] = {'items':[{'id':'one'}],'ready_frontier':['one']}
        work_path.write_text(json.dumps(work_plan))
        self.assertEqual(['build'],plan(workflow_path,self.examples/'feature-run.json',AT)['ready'])
        work_plan['payload']['ready_frontier'] = []
        work_path.write_text(json.dumps(work_plan))
        self.assertEqual('blocked',plan(workflow_path,self.examples/'feature-run.json',AT)['status'])

    def test_code_recovery_does_not_require_unselected_data_authority(self):
        workflow = {'schema_version':'1.0','id':'recovery','summary':'Scoped code recovery.',
            'inputs':['request','deployment-record'], 'completion':['recover'],
            'steps':[{'id':'recover','skill':'sf-recover-release','needs':[],
                'bindings':{'request':'input:request','deployment-record':'input:deployment-record'}}]}
        workflow_path = self.base / 'recovery.json'
        workflow_path.write_text(json.dumps(workflow))
        contract = contracts()['sf-recover-release']
        self.edit('feature-run.json', lambda p: p.update(capabilities=contract['capabilities'],
            inputs={'request':'records/request.json','deployment-record':'records/deployment-record.json'},
            effect_scopes={'deployment.modify':'environment:demo-staging'}))
        def recovery_policy(p):
            grant = deepcopy(p['grants'][0])
            grant.update(id='recovery-grant',effect='deployment.modify',scope='environment:demo-staging')
            p['grants'] = [grant]
            p['required_artifacts']['deployment.modify'] = ['deployment-record']
        self.edit('policy.json',recovery_policy)
        self.assertEqual(['recover'],plan(workflow_path,self.examples/'feature-run.json',AT)['ready'])
        self.edit('feature-run.json',lambda p:p.update(selected_effects={'recover':['data.modify']}))
        result = plan(workflow_path,self.examples/'feature-run.json',AT)
        self.assertEqual('blocked',result['status'])
        self.assertIn('data.modify',' '.join(result['blocked']['recover']))
        self.edit('feature-run.json',lambda p:p.update(selected_effects={'recover':['workspace.modify']}))
        with self.assertRaisesRegex(ValueError,'not declared conditional'):
            plan(workflow_path,self.examples/'feature-run.json',AT)


if __name__ == '__main__':
    unittest.main()
