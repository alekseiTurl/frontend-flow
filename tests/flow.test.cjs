'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const {check} = require('../skills/frontend-flow/scripts/check-flow.cjs');
const {reminder} = require('../skills/frontend-flow/scripts/session-start.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');

function workspace(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'frontend-flow-check-'));
  t.after(() => {
    assert.equal(path.dirname(dir), path.resolve(os.tmpdir()));
    assert(path.basename(dir).startsWith('frontend-flow-check-'));
    fs.rmSync(dir, {recursive: true, force: true});
  });
  return dir;
}
function fixture(t) {
  const dir = workspace(t);
  const files = {'plan.md': 'Approved plan fixture', 'review.md': 'Review evidence fixture',
    'commit-message.md': 'Commit draft', 'mr-description.md': 'MR draft', 'ui-testing.md': 'Browser evidence fixture'};
  for (const [name, body] of Object.entries(files)) fs.writeFileSync(path.join(dir, name), body);
  const state = {schema_version: 2, plan_version: 1,
    approval: {version: 1, plan_sha256: hash(files['plan.md']), user_message: 'Fixture consent', recorded_at: '2026-10-08T12:00:00Z'},
    findings: [], checks: [{name: 'playwright-ui', required: true, status: 'passed', evidence: 'UI fixture'}],
    agents: {frontend_writer: {id: 'writer'}, frontend_tester: {id: 'tester'}},
    review: {final_verified: true, evidence: 'Verified fixture', snapshot: 'snapshot-1'},
    ui_testing: {required: true, reason: 'Changed UI', check_name: 'playwright-ui', snapshot: 'snapshot-1', agent_id: 'tester'},
    writing: {author_role: 'frontend_writer', agent_id: 'writer', review_snapshot: 'snapshot-1',
      artifacts: {'commit-message.md': hash(files['commit-message.md']), 'mr-description.md': hash(files['mr-description.md'])}}};
  return {dir, state, save: () => fs.writeFileSync(path.join(dir, 'state.json'), JSON.stringify(state))};
}
const cases = [
  ['passed UI', () => {}, null],
  ['non-UI task', s => {s.ui_testing = {required: false, reason: 'Documentation'}; s.checks = [];}, null],
  ['missing classification', s => {delete s.ui_testing;}, /classification/],
  ['pending classification', s => {s.ui_testing.required = null;}, /classification/],
  ['missing UI check', s => {s.checks = [];}, /UI check missing/],
  ['optional UI check', s => {s.checks[0].required = false;}, /UI check missing/],
  ['failed UI', s => {s.checks[0].status = 'failed';}, /Required check not passed/],
  ['blocked UI', s => {s.checks[0].status = 'blocked';}, /Required check not passed/],
  ['stale UI snapshot', s => {s.ui_testing.snapshot = 'old';}, /different source snapshot/],
  ['missing tester', s => {delete s.agents.frontend_tester;}, /tester record/],
  ['wrong tester', s => {s.ui_testing.agent_id = 'other';}, /tester record/],
  ['duplicate UI check', s => {s.checks.push({...s.checks[0]});}, /duplicate/],
  ['waiver without consent', s => {s.checks[0].status = 'waived';}, /Missing user waiver/],
  ['explicit waiver', s => {s.checks[0].status = 'waived'; s.checks[0].user_message = 'Fixture waiver'; s.ui_testing.snapshot = null;}, null],
  ['unresolved finding', s => {s.findings = [{id: 'F1', evidence: 'fixture', status: 'open'}];}, /Unresolved finding/],
  ['writer mismatched snapshot', s => {s.writing.review_snapshot = 'old';}, /different reviewed snapshot/]
];
for (const [name, mutate, error] of cases) test(name, t => {
  const f = fixture(t); mutate(f.state); f.save();
  if (error) assert.throws(() => check('check-done', f.dir), error);
  else assert.equal(check('check-done', f.dir).ok, true);
});
test('plan changed after consent', t => {
  const f = fixture(t); f.save(); fs.appendFileSync(path.join(f.dir, 'plan.md'), 'changed');
  assert.throws(() => check('check-plan', f.dir), /Plan changed/);
});
test('empty UI report', t => {
  const f = fixture(t); f.save(); fs.writeFileSync(path.join(f.dir, 'ui-testing.md'), '');
  assert.throws(() => check('check-done', f.dir), /Empty ui-testing/);
});
test('writer text tampering', t => {
  const f = fixture(t); f.save(); fs.appendFileSync(path.join(f.dir, 'commit-message.md'), 'changed');
  assert.throws(() => check('check-done', f.dir), /Writer artifact changed/);
});
test('legacy plan integrity remains supported', t => {
  const f = fixture(t); f.state.schema_version = 1; delete f.state.ui_testing; f.save();
  assert.equal(check('check-plan', f.dir).ok, true);
});
test('hook ignores unrelated events and absent state', t => {
  const dir = workspace(t);
  assert.deepEqual(reminder({hook_event_name: 'Stop', cwd: dir}), {});
  assert.deepEqual(reminder({hook_event_name: 'SessionStart', cwd: dir}), {});
});
test('hook finds parent state without importing task content', t => {
  const dir = workspace(t);
  fs.mkdirSync(path.join(dir, '.frontend-flow')); fs.mkdirSync(path.join(dir, 'src'));
  fs.writeFileSync(path.join(dir, '.frontend-flow', 'untrusted.txt'), 'UNTRUSTED_CONTENT');
  const result = reminder({hook_event_name: 'SessionStart', cwd: path.join(dir, 'src')});
  assert(result.hookSpecificOutput.additionalContext.includes('.frontend-flow'));
  assert(!JSON.stringify(result).includes('UNTRUSTED_CONTENT'));
});
test('hook stops at nested repository boundary', t => {
  const dir = workspace(t);
  fs.mkdirSync(path.join(dir, '.frontend-flow')); fs.mkdirSync(path.join(dir, 'nested'));
  fs.writeFileSync(path.join(dir, 'nested', '.git'), 'gitdir: external');
  assert.deepEqual(reminder({hook_event_name: 'SessionStart', cwd: path.join(dir, 'nested')}), {});
});
