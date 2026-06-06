# LLMS.txt Launch Kit — Free Sample

Generate and validate a clean `llms.txt` file from a URL list, local Markdown folder, or sitemap.

This repo is the free sample for the LLMS.txt Launch Kit. It includes the core local CLI and a small SaaS/docs example. The paid full pack adds editable templates, checklists, review prompts, GitHub Actions, and an `llms-full.txt` pattern.

## Why This Exists

`llms.txt` is a Markdown file published at `/llms.txt` that helps AI assistants and tools understand the important public resources on a website.

Online generators are useful, but many teams still need to:

- choose which pages belong in the file
- remove noisy or private URLs
- write useful descriptions
- validate the file before publishing
- keep the workflow local and reviewable

This sample focuses on that workflow.

## Included

- `tools/llms_kit.py`: dependency-free Python CLI
- `examples/url-list.txt`: editable URL list
- `examples/free-saas-llms.txt`: example output
- `.github/workflows/validate-example.yml`: CI check for the example file

## Quick Start

```sh
python3 tools/llms_kit.py generate \
  --title "Example SaaS" \
  --description "Example SaaS helps teams organize product docs for customers and AI assistants." \
  --base-url "https://acme.example" \
  --url-list examples/url-list.txt \
  --output-dir /tmp/llms-sample

python3 tools/llms_kit.py validate /tmp/llms-sample/llms.txt
```

## URL List Format

Each non-comment line uses:

```text
url | title | description | section
```

Example:

```text
/docs/getting-started.md | Getting Started | Account setup and first workflow. | Docs
```

## Publish

Upload the generated file to:

```text
https://your-site.com/llms.txt
```

Optionally mirror it at:

```text
https://your-site.com/.well-known/llms.txt
```

## Full Pack

The full LLMS.txt Launch Kit includes:

- 5 editable templates: SaaS docs, API docs, e-commerce, local service, personal site
- launch checklist
- content audit checklist
- AI creation and review prompts
- GitHub Actions workflow
- minimal `llms-full.txt` example

Full pack: https://boltonmejia.gumroad.com/l/llms-txt-launch-kit

## Important

This does not guarantee ranking or inclusion in ChatGPT, Claude, Perplexity, Google AI Overviews, or any search product. It helps you publish a clean, structured, public context file that tools, assistants, and directories can discover.
