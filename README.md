# lccli

A CLI prototype for `leetcode.cn` that supports:

- logging into an existing LeetCode CN session
- fetching problems and generating local files
- running sample cases locally
- running code remotely
- submitting solutions

## Current Scope

This version focuses on the stable path:

- login does not simulate username/password flows
- authentication uses cookies from an already signed-in browser session
- problem metadata is fetched through `https://leetcode.cn/graphql/`
- remote run/submit uses the current web endpoints:
  - `POST /problems/<slug>/interpret_solution/`
  - `POST /problems/<slug>/submit/`
  - `GET /submissions/detail/<id>/check/`

That tradeoff is intentional. LeetCode login typically involves captcha, risk controls, SMS, or third-party auth, so a direct credential-based CLI flow is brittle and expensive to maintain.

## Installation

From the repository root:

```bash
pip install -e .
```

Or run it directly as a module:

```bash
python3 -m lccli --help
```

## Login

First sign in to `https://leetcode.cn` in your browser, then copy the `Cookie` header from the browser devtools. At minimum it should include:

- `LEETCODE_SESSION`
- `csrftoken`

Example:

```bash
lccli login --cookie 'LEETCODE_SESSION=...; csrftoken=...'
```

Or load the cookie string from a file:

```bash
lccli login --cookie-file cookies.txt
```

The config is stored at:

```text
~/.config/lccli/config.json
```

Check the current session:

```bash
lccli whoami
```

## Fetch Problems

Fetch a problem by slug and generate local files:

```bash
lccli fetch two-sum --lang python3
```

You can also pass a full problem URL:

```bash
lccli fetch https://leetcode.cn/problems/two-sum/description/ --lang python3
```

Generated files look like this:

```text
0001-two-sum/
  README.md
  README_ZH.md
  problem.json
  solution.py
```

File layout:

- `README.md`: English statement
- `README_ZH.md`: Chinese statement

## Local Testing

Use this before submitting. Local testing currently supports:

- `python3`
- `cpp`

The current implementation targets common `Solution.method(...)` style problems and covers:

- primitive types
- arrays / matrices
- `ListNode`
- `TreeNode`

By default, the tool tries to extract sample inputs and expected outputs from the problem statement:

```bash
lccli test two-sum --file 0001-two-sum/solution.py
```

You can also provide manual test input:

```bash
lccli test two-sum --file 0001-two-sum/solution.py --testcase $'[2,7,11,15]\n9' --expected '[0,1]'
```

If you pass `--testcase` without `--expected`, the command will print the actual output without marking pass/fail.

## Remote Run

By default, this uses the problem's `sampleTestCase`:

```bash
lccli run two-sum --file 0001-two-sum/solution.py
```

You can also provide custom input:

```bash
lccli run two-sum --file 0001-two-sum/solution.py --testcase $'[2,7,11,15]\n9'
```

Or read it from a file:

```bash
lccli run two-sum --file 0001-two-sum/solution.py --testcase-file testcase.txt
```

## Submit

```bash
lccli submit two-sum --file 0001-two-sum/solution.py
```

## Languages

List remote languages:

```bash
lccli langs
lccli langs --json
```

## Local Toolchains

Inspect which local runtimes and toolchains are available for future local execution:

```bash
lccli doctor
lccli doctor --json
```

This does not enable local testing for every language by itself. It only reports whether the required local commands appear to be installed.

## Known Limitations

- This is currently tailored to `leetcode.cn`.
- Login is cookie-based, not username/password based.
- Local `test` currently supports `python3` and `cpp` only.
- `run` and `submit` depend on the current LeetCode web endpoints and may need updates if the site changes.
- Problem lookup currently accepts a slug or problem URL, not a numeric problem id.
- Problem statements are written to Markdown with minimal HTML cleanup.

## Next Steps

If you want to keep building this into a durable CLI, the next practical steps are:

1. Add `browser login` to open the login page locally and collect cookies afterward.
2. Add a local cache for `frontend id -> slug`.
3. Expand the `test` subcommand for broader local execution support.
4. Improve terminal rendering for run/submit results.
5. Generate richer local templates for common languages.
