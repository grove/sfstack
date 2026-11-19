# Operate a factory controller

Use this guide when building a controller around sfstack. The repository supplies
skills, contracts, workflow recipes, validation, and offline reference checks.
The controller is responsible for executing work safely against real services.

## 1. Establish the run

Select a workflow and validate it before execution. Resolve every external input
and capture an immutable subject: source revision, relevant input digest, and
target environment. Record the selected skill versions, available adapters,
actual authorization, and finite budget.

Choose an explicit completion boundary. Finishing a feature recipe yields a
review package. Integrating and deploying belong to the release process. A
migration or retirement plan does not mean that live data has changed.

Select any declared conditional effects needed by this invocation. For example,
recovery that restores persistent data selects `data.modify` for its recovery
step; deployment-only recovery does not. All baseline effects still apply. An
unselected conditional effect is prohibited, so a newly discovered need requires
a revised scoped invocation before execution.

## 2. Schedule only ready work

A node is eligible after its prerequisites have satisfied their contracts and
all required artifact bindings resolve. A ready node still needs capability,
permission, and resource-ownership checks before execution. Never interpret a
workflow edge as a grant to perform the next external action.

Respect each node's work-item bound. The included feature and defect recipes
limit their implementation node to one item. When a plan has several items,
expand it into separately owned work units and a deliberate integration/verification
join. Preserve the parent plan and acceptance criteria. A controller cannot mark
the whole feature complete after one unit merely because a recipe's last node
finished.

Parallelize independent read-only work or isolated changes. Assign a single
owner to each mutable candidate, review request, deployment, and shared item.
Use expiring leases and compare-and-set updates so a recovered controller cannot
silently race an older worker.

## 3. Execute with durable boundaries

Persist the intended operation before dispatch and the observed outcome after
completion. For external writes, use an idempotency key where supported and
reconcile unknown outcomes before retrying. Enforce target and scope restrictions
in adapters at the point of action.

Capture command identity, parameters safe to retain, environment, result, and
artifacts without copying credentials or unnecessary sensitive data. Store
content hashes to detect later edits, while recognizing that a hash does not
prove a command actually ran.

## 4. Evaluate results before advancing

Validate the artifact envelope, producer, version, subject, checks, and evidence.
Apply policy to the action being considered. Confirm that required reviews and
checks apply to the exact candidate, and that unresolved findings have an
explicit disposition.

A passing plan describes a complete plan. A passing review says the review
criteria were met. Neither independently proves a deployed system is healthy.
Keep evidence types and claims aligned.

The reference planner uses a conservative fixed-subject checkpoint. When source,
inputs, or environment change, explicitly revalidate or establish a new
checkpoint. It does not implement automatic incremental replay. A richer
controller may track dependencies more precisely, but must never relabel stale
evidence as current without performing the necessary work.

## 5. Recover deliberately

| Observed condition | Controller response |
| --- | --- |
| Worker stopped before producing a result | Reconcile workspace and external operations, then resume under a new lease. |
| A tool timed out after a write | Query the operation identity before retrying. |
| Required capability or permission missing | Mark blocked and identify the needed capability or scoped decision. |
| Evidence missing, stale, or insufficient | Mark inconclusive or blocked; rerun the relevant check after repair. |
| Behavior fails a criterion | Mark failed, retain the evidence, and schedule a bounded repair. |
| Another actor changed the item or candidate | Reload, preserve their work, reconcile scope, and revalidate. |
| Budget exhausted | Stop dispatch, persist the handoff, and report remaining work. |

Do not resume an expired grant automatically. Check the grant's scope and current
validity. Break-glass procedures need an explicit local policy and durable record.
Use a separately owned recovery policy when emergency preconditions differ from
normal release requirements. Workers must not weaken policy or manufacture
waivers to overcome a blocked gate.

## 6. Verify external outcomes

After an integration, inspect the resulting revision. After deployment, identify
the actual deployed revision and environment before evaluating health. After
recovery, verify behavior and data compatibility; a successful command exit alone
is insufficient.

Use `sf-observe-release`, `sf-recover-release`, and `sf-handle-incident` for their
respective responsibilities. Define observation duration, alert ownership, and
response thresholds before relying on unattended rollout.

## 7. Qualify before broadening autonomy

Run representative end-to-end tasks in isolation. Include stale-head races,
duplicate event delivery, worker crashes, provider outages, wrong-environment
requests, and compromised input text. Record both successful outcomes and refused
unsafe transitions. Broaden the scope only after the relevant boundary has been
exercised. See [factory architecture](../explanation/factory-design.md).
