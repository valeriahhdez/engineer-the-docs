---
title : "Docs as code, DocOps, and docs engineering: what they are and how they relate"
---


Docs-as-code (DaC), documentation operations (DocOps), and docs engineering (DocEng). These terms are often confused and used interchangeably. But they are not synonyms. Understanding how they relate to each other is the first step toward understanding what modern documentation practice actually looks like.

### Docs-as-code (DaC): The methodology

DaC is a methodology for managing documentation as code. These are core principles for treating documentation: 
- Wirtten in plain text (typically Markdown or reStructuredText).
- Version-controlled (typically with Git).
- Reviewed through workflows the same way code does (pull requests, approvals, merge).
- Built and deployed automatically rather than published manually.

This approach is not tied to any particular tool. You can practice docs as code with MkDocs, Docusaurus, Sphinx, Hugo, GitBook, Mintlify or dozens of other static site generators. The generator is a tool. What defines the methodology is the workflow, not the toolchain.

Docs as code also has implications for where documentation lives. When your docs are Markdown files in a Git repository, they can live in the same repository as the software they describe or in a monorepo or a tightly coupled satellite repo. That proximity changes the relationship between documentation and code in ways that are harder to achieve when docs live in a separate platform.