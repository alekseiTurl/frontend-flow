# Persistent state contract

state.json is coordinator bookkeeping, not proof of user identity or permission. Verify consent/rejections against actual conversation messages. If unavailable, ask the user to reaffirm the saved plan; do not recreate it.

New tasks use schema 2. On resuming unfinished schema 1, preserve plan bytes, hash, consent, baseline, findings and checks; set schema_version=2, add routing/writing, and have the architect classify only remaining work if needed. Retire saved legacy frontend_developer IDs; preserve their implementation evidence. Reuse an existing reviewer only if its model/effort and instructions match this workflow (including no writing); otherwise start an independent replacement with saved evidence. A previously approved plan needs no new approval solely for migration/tier selection. Completed schema-1 records stay historical until work resumes. The checker accepts schema 1 for plan integrity but requires migration for completion.

```json
{
  "schema_version": 2,
  "task_id": "filter-products",
  "project_root": "absolute project path",
  "phase": "architecture",
  "plan_version": 1,
  "approval": null,
  "baseline": {"head": "actual SHA", "comparison": "actual comparison", "dirty_changes_report": "baseline.md"},
  "agents": {},
  "routing": [],
  "findings": [],
  "checks": [],
  "ui_testing": {"required": null, "reason": null, "check_name": "playwright-ui", "snapshot": null, "agent_id": null},
  "review": {"final_verified": false, "snapshot": null},
  "writing": null
}
```

В ходе работы сохраняйте в state.json список temporary_paths с абсолютными путями временных файлов/каталогов, созданных задачей, если они находятся вне её служебного каталога. Не включайте исходники, существовавшие ранее файлы и итоговые пользовательские результаты. Этот список нужен только для очистки и не является снимком кода или обязательным полем check-done.

Phases: architecture, clarifying, awaiting_approval, development, ui_testing, review, fixes, awaiting_decision, writing, awaiting_completion, complete.

Approval: `{ "version": 1, "plan_sha256": "SHA-256 of plan.md bytes", "user_message": "exact user approval", "turn_ref": null, "recorded_at": "ISO timestamp" }`. Hash using Get-FileHash or Node crypto. Store clarification decisions briefly in plan.md; unresolved required questions keep phase=clarifying.

Agent entry, keyed by role: `{ "id": "actual returned ID", "model": "gpt-5.6-luna", "effort": "medium", "assignment": "owned scope" }`. Keep prior IDs in routing history on replacement. Routing entries record package/scope, junior|middle|senior|bugfixer, the routing decision/reason and any escalation handoff paths; do not rewrite an approved plan merely to record routing changes.

Bugfixer routing: record agents.frontend_bugfixer with its actual ID/model/effort. For an initial defect-fixing package record the architect decision; for defects found during testing/review record the coordinator handoff, finding IDs, owned scope and prior attempts. Use phase=fixes for follow-up repairs and append concise results to implementation.md. Reuse the same bugfixer for later rounds. Preserve existing agent IDs/evidence in routing history; never reset attempt counts on handoff. After fixes invalidate review.final_verified, writing and ui_testing.snapshot under the existing source-change rules. The reviewer alone verifies finding closure. Existing plan approval remains valid for a handoff within unchanged scope; do not edit approved plan bytes to update agent metadata.

Finding: `{ "id": "F1", "priority": "P2", "evidence": "file, lines, trigger", "status": "open", "resolution": null }`. Statuses: open, fixing, disputed, fixed_verified, rejected_by_user. A verified fix needs resolution.evidence from the reviewer. A rejection needs resolution.user_message and resolution.reason from actual the user evidence.

Check: `{ "name": "typecheck", "command": "actual command", "required": true, "status": "passed", "evidence": "actual outcome" }`. Statuses: passed, failed, blocked, waived. Waived needs user_message and evidence explaining why. Omit inapplicable checks rather than marking them passed. Include every required project/plan check; the checker cannot discover omissions.

UI testing: before check-done, classify UI impact in ui_testing.required (boolean) and reason (nonempty). For UI changes set required=true, add a required check named playwright-ui, and record the frontend_tester ID, tested snapshot and report in ui-testing.md. A passed check requires ui_testing.agent_id matching agents.frontend_tester.id and ui_testing.snapshot matching review.snapshot. A blocked or failed UI check prevents completion unless explicitly waived by the user under the existing check rules. For required=false explain why the actual change does not affect UI; no tester report is required. The reviewer verifies this classification. The checker validates records, not the actual browser session or completeness of scenarios.

For unfinished schema-2 tasks missing ui_testing, add this field before completion without changing approved plan bytes; classify actual UI impact and perform applicable checks. Preserve prior evidence; scenarios outside the approved scope follow ordinary planning rules. Do not migrate awaiting_completion/complete tasks solely for cleanup. After source edits clear ui_testing.snapshot. The tester must rerun affected scenarios or document why previous evidence remains applicable before binding it to the new snapshot.

Snapshot: use a deterministic identifier covering HEAD, exact comparison, staged/working-tree source diff and relevant untracked source contents, excluding secret contents and workflow artifacts. Document the method, explicit safe paths, omissions and comparison in review.md so it can be reproduced. Do not treat HEAD alone as a dirty-worktree snapshot. A secret-related change that cannot be safely reviewed is a reported coverage gap, not silently verified. Before presenting the final result, the coordinator verifies the snapshot unchanged before and after writing; review.snapshot contains that identifier, review.final_verified=true, and review.evidence records the actual final check.

After frontend_writer returns both artifact bodies, the coordinator saves them verbatim and records:

```json
{
  "author_role": "frontend_writer",
  "agent_id": "actual writer ID matching agents.frontend_writer.id",
  "review_snapshot": "same identifier as review.snapshot",
  "artifacts": {
    "commit-message.md": "SHA-256 of saved bytes",
    "mr-description.md": "SHA-256 of saved bytes"
  }
}
```

Store this object as state.writing. Any later source edit clears review.final_verified and writing. Any writer text correction requires updated hashes. Completion requires review.md, both writer artifacts, resolved findings and passing/explicitly waived required checks. Run check-done once after saving the final writer artifacts and before deleting plan.md or setting phase=awaiting_completion. Immediately after it passes, delete the task plan and its task-created temporary copies as specified in SKILL.md; no completion confirmation is needed for plan cleanup. It checks recorded integrity, not actual authorship, consent, code quality or live source; the coordinator must establish those from tool/user evidence.

awaiting_completion означает, что проверки пройдены и полные тексты writer показаны в чате, но пользователь ещё не подтвердил завершение. На этом этапе plan.md и его временные копии уже удалены; сохраняйте остальные артефакты. Отсутствие плана здесь ожидаемо: при возобновлении awaiting_completion не восстанавливайте его и не запускайте check-plan/check-done повторно только ради завершения или очистки. Если пользователь запросил новые доработки, восстановите точный ранее одобренный план из доступного контекста с совпадающим хешем либо подготовьте новый план и согласуйте его в обычном порядке; не обходите проверку плана перед изменением кода. После явного подтверждения сохраните completion = {"user_message": "точный текст подтверждения", "turn_ref": null, "recorded_at": "ISO timestamp"}, проверьте его по реальному сообщению пользователя, затем установите phase=complete и выполните только очистку из SKILL.md. Не проверяйте повторно diff, snapshot, хеши, check-done и результаты проверок после подтверждения завершения. Для задачи в phase=complete с оставшимися временными файлами продолжайте только очистку; повторять этапы разработки, ревью или writing для этого не нужно. Запись completion сама по себе не доказывает согласие. Не требуется новая версия схемы: это дополнительное поле. После успешной очистки state.json и прочие служебные файлы задачи отсутствуют; не восстанавливайте их автоматически для хранения истории. Для ранее завершённых задач с сохранившимися файлами сначала покажите финальные тексты в чате и получите подтверждение очистки, если его ещё не было.

Developer role rename: frontend_middle -> middle_dev (Middle Dev), frontend_senior -> senior_dev (Senior Dev). Preserve approved plan bytes and prior IDs/evidence; record the mapping in routing history and use the new role names for future dispatch. Labels junior|middle|senior describe complexity tiers. New routine packages may use junior_dev; existing middle_dev records remain historical and are not renamed to junior. Preserve previous actual models/effort and approved plan bytes; record a new routing entry when changing the assigned role/model. Junior handoffs may go directly to middle or senior after the architect classifies the remainder; attempt counts continue across agents. Do not rename frontend_writer or its completion records. Standalone review/writing does not create or migrate this state.
