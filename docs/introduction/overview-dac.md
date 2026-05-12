---
title : "Docs as code, DocOps, and docs engineering: what they are and how they relate"
---


Docs-as-code (DaC), documentation operations (DocOps), and docs engineering (DocEng) are often confused and used interchangeably. But they are not synonyms. This article explains what they are and how they relate to each other.

## Docs-as-code (DaC): The methodology

DaC is a methodology for managing documentation as code. These are its core principles for treating documentation:

- Write in plain text (typically Markdown or reStructuredText).
- Use version-control (typically with Git).
- Review through workflows the same way code does (pull requests, approvals, merge).
- Build and deploy automatically rather than published manually.

This approach is tool agnostic. You can practice docs as code with Zensical, Docusaurus, Sphinx, Hugo, GitBook, Mintlify or other static site generators. What defines the methodology is the workflow, not the toolchain.

DaC also has implications for where documentation lives. Markdown-based documentation can live directly within the software's repository or in a dedicated, linked repository. That proximity changes the relationship between documentation and code in ways that are harder to achieve when docs live in a separate platform.

## Documentation operations (DocOps): The operational layer

DocOps is what DaC looks like when it is running. The term borrows from [DevOps](https://en.wikipedia.org/wiki/DevOps) and refers to the same shift applied to documentation: move from manual, handoff-driven processes toward automated, continuously-integrated ones.

A DocOps pipeline typically includes a CI/CD system (GitHub Actions is common) that triggers on every pull request or merge. That pipeline runs quality gates, for example, a linter like Vale checking against your style guide. It deploys the output to a hosting environment like GitHub Pages, Netlify, or Cloudflare Pages, and may also run accessibility checks, spell checking, or custom validation scripts.

The feedback loop is the key concept here. In a mature DocOps setup, a writer submitting a pull request (PR) in GitHub gets automated feedback within seconds, for example: 

_This heading violates the style guide._ 

The quality gate runs before a human reviewer ever looks at the content. That changes the economics of documentation review substantially.

DocOps is not optional overhead on top of DaC. It is what makes docs as code sustainable. Without automation, the DaC workflow is just more steps. DocOps is the operational layer that convert those steps into a system.

## Docs engineer (DocEng): The owner

A docs engineer (DocsEng) is not a writing role that uses Git. It is an engineering role that happens to own documentation infrastructure. 

These are some tasks a DocsEng owns:

- Configures CI/CD pipelines.
- Writes Vale style rules.
- Builds custom MkDocs plugins.
- Integrates documentation tooling into developer workflows.

DocsEngs thinks about the documentation platform the way a platform engineer thinks about infrastructure: as a system that other people depend on and that needs to be reliable, maintainable, and extensible.

The skill profile reflects this. A DocEng needs technical writing fluency but they also need enough engineering capability to own a pipeline, debug a failed build, write a GitHub Actions workflow, and make architectural decisions about the toolchain. The role sits at the intersection of engineering and tech writing. But it is a different job than either pure technical writing or pure software engineering.

## How these concepts are related

An organization can adopt docs as code without a dedicated docs engineer — writers can commit Markdown, open pull requests, and publish via a static site generator with minimal automation. Many teams work this way. But that team is not doing DocOps in any meaningful sense; they have adopted the file format and the workflow without building the operational layer.

A docs engineer, by contrast, always works within a DocOps frame. You cannot meaningfully own a documentation platform without thinking in terms of pipelines and quality gates. The role presupposes the practice.

## What this looks like in practice

A team early in the transition typically starts with docs as code: pick a static site generator, migrate content to Markdown, put the repo on GitHub. That is enough to unlock the workflow benefits — version history, diff review, branching strategies — without committing to a full pipeline.

As the workflow matures, the DocOps layer gets added incrementally. A basic CI check that runs Vale on pull requests. A link checker that runs on merge. A deployment pipeline that publishes automatically on push to main. Each addition extends the system's ability to maintain quality at scale without increasing the review burden on individual humans.

The docs engineering function emerges — either as a dedicated role or as a responsibility distributed across a team — when the platform itself becomes a thing that needs maintenance and development. Someone has to own the Vale rule set and update it when the style guide changes. Someone has to update the  plugins when a dependency breaks. Someone has to think about whether the toolchain is still the right toolchain as the documentation grows.

That ownership is what docs engineering describes: not just using the tools, but being responsible for them.