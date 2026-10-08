#!/usr/bin/env node
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
function check(mode, dir) {
  if (!['check-plan', 'check-done'].includes(mode) || !dir) throw Error('Usage: node check-flow.cjs check-plan|check-done <task-dir>');
  const s = JSON.parse(fs.readFileSync(path.join(dir, 'state.json'), 'utf8'));
  const text = x => typeof x === 'string' && x.trim().length > 0;
  const requireThat = (ok, message) => { if (!ok) throw Error(message); };
  requireThat([1, 2].includes(s.schema_version), 'Unsupported state schema');
  requireThat(Number.isInteger(s.plan_version) && s.plan_version > 0, 'Invalid plan version');
  const plan = fs.readFileSync(path.join(dir, 'plan.md'));
  requireThat(plan.toString('utf8').trim().length > 0, 'Empty plan');
  const hash = crypto.createHash('sha256').update(plan).digest('hex');
  const a = s.approval;
  requireThat(a && a.version === s.plan_version && text(a.user_message) && text(a.recorded_at), 'Explicit approval record missing or version mismatch');
  requireThat(typeof a.plan_sha256 === 'string' && a.plan_sha256.toLowerCase() === hash, 'Plan changed since approval');
  if (mode === 'check-done') {
    requireThat(s.schema_version === 2, 'Migrate unfinished schema-1 task to schema 2 before completion');
    requireThat(Array.isArray(s.findings) && Array.isArray(s.checks), 'Missing findings/checks ledger');
    const ids = new Set();
    for (const f of s.findings) {
      requireThat(text(f.id) && !ids.has(f.id), 'Missing or duplicate finding ID'); ids.add(f.id);
      requireThat(text(f.evidence), `Missing finding evidence: ${f.id}`);
      requireThat((f.status === 'fixed_verified' && text(f.resolution?.evidence)) ||
        (f.status === 'rejected_by_user' && text(f.resolution?.user_message) && text(f.resolution?.reason)), `Unresolved finding: ${f.id}`);
    }
    for (const c of s.checks) {
      requireThat(text(c.name) && typeof c.required === 'boolean' && ['passed','failed','blocked','waived'].includes(c.status), 'Invalid check entry');
      requireThat(text(c.evidence), `Missing check evidence: ${c.name}`);
      if (c.status === 'waived') requireThat(text(c.user_message), `Missing user waiver: ${c.name}`);
      if (c.required) requireThat(c.status === 'passed' || c.status === 'waived', `Required check not passed: ${c.name}`);
    }
    requireThat(s.review?.final_verified === true && text(s.review.evidence), 'Final review verification missing');
    requireThat(text(s.review.snapshot), 'Reviewed source snapshot missing');
    const ui = s.ui_testing;
    requireThat(typeof ui?.required === 'boolean' && text(ui.reason), 'UI impact classification missing');
    if (ui.required) {
      requireThat(ui.check_name === 'playwright-ui', 'UI check name missing');
      const uiChecks = s.checks.filter(c => c.name === ui.check_name);
      requireThat(uiChecks.length === 1 && uiChecks[0].required === true, 'Required UI check missing or duplicate');
      const uiCheck = uiChecks[0];
      requireThat(['passed', 'waived'].includes(uiCheck.status), 'UI verification not passed');
      if (uiCheck.status === 'passed') {
        requireThat(text(ui.agent_id) && ui.agent_id === s.agents?.frontend_tester?.id, 'Dedicated tester record missing or agent mismatch');
        requireThat(ui.snapshot === s.review.snapshot, 'UI verification belongs to a different source snapshot');
        requireThat(fs.readFileSync(path.join(dir, 'ui-testing.md'), 'utf8').trim().length > 0, 'Empty ui-testing.md');
      }
    }
    const w = s.writing;
    requireThat(w?.author_role === 'frontend_writer' && text(w.agent_id) &&
      w.agent_id === s.agents?.frontend_writer?.id, 'Dedicated writer record missing or agent mismatch');
    requireThat(w.review_snapshot === s.review.snapshot, 'Writing belongs to a different reviewed snapshot');
    requireThat(fs.readFileSync(path.join(dir, 'review.md'), 'utf8').trim().length > 0, 'Empty review.md');
    for (const name of ['commit-message.md', 'mr-description.md']) {
      const body = fs.readFileSync(path.join(dir, name));
      requireThat(body.toString('utf8').trim().length > 0, `Empty ${name}`);
      const expected = w.artifacts?.[name];
      requireThat(typeof expected === 'string' && expected.toLowerCase() ===
        crypto.createHash('sha256').update(body).digest('hex'), `Writer artifact changed or hash missing: ${name}`);
    }
  }
  return {ok: true, mode, plan_sha256: hash};
}
module.exports = {check};
if (require.main === module) {
  try { console.log(JSON.stringify(check(process.argv[2], process.argv[3]))); }
  catch (e) { console.error(e.message); process.exitCode = 1; }
}
