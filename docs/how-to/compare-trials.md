# Compare agent configurations

Measure whether sfstack changes outcomes, not only the number of artifacts.
Use an isolated task and a grader independent of the worker. Execute the same
tasks with **bare agent**, **skill instructions only**, and **skills plus
contracts and gates**. Keep model, agent settings, tools, task, environment,
and scoring rules fixed across each triplet. Randomize execution order and
repeat seeds where possible.

Record each observation with `case_id`, `trial_id`, `variant`,
`agent`, and `environment`. Record verified correctness, unsupported
completion claims, human intervention count, elapsed seconds, USD cost,
recovery success, and safety violations.

Validate and summarize:

```sh
python tools/compare_trials.py --input examples/comparative-trials-synthetic.json
```

The example is **invented data to illustrate output shape**. It is not a
benchmark or evidence that sfstack improves correctness. The script rejects
unpaired and duplicate trials or mixed agent/environment values within a
triplet, then reports descriptive per-variant averages and paired differences.
It does not execute an LLM, authenticate observations, measure significance,
or correct for dataset selection. Retain grader output separately and do not
turn blocked/inconclusive tasks into a passing `correct` value.

Use the [seed case](../../evals/README.md) for a first isolated exercise,
then expand to held-out multi-language tasks and adversarial controller
conditions before drawing conclusions.
