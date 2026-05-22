---
title: Home
hide:
  - navigation
  - toc
---



<div class="hero-container">
  <div class="hero-content">
    <h1>Engineer the docs</h1>
    <p>Discover how technical writing evolves into documentation engineering. Find practical insights, hands-on experiments, and lessons learned along the journey.</p>
    <a href="{url}" class="md-button">Start your journey</a>
  </div>
  <div class="hero-image">
    <img src="assets/images/logo.png" alt="Brand identity visual">
  </div>
</div>

<h2>Explore resources</h2>
<div class="card-grid">
  <a href="path/to/api/page.md" class="card">
    <img src="assets/images/icons/play-circle-dark.svg" class="card-icon icon-dark" alt="Play symbol card image">
    <img src="assets/images/icons/play-circle-light.svg" class="card-icon icon-light" alt="Play symbol card image">
    <div class="card-content">
      <div class="card-title">New to docs engineering?</div>
      <div class="card-description">Learn the fundamentals of docs enginering, docs as code, and DocOps.</div>
    </div>
  </a>
  <a href="path/to/custom-apps/page.md" class="card">
    <img src="path/to/your/custom-apps-image.svg" alt="Custom Apps card image">
    <div class="card-content">
      <div class="card-title">Build your docs pipeline</div>
      <div class="card-description">Learn how to add quality gates and automate docs tasks.</div>
    </div>
  </a>
</div>

## Project layout

```yaml title="mkdocs.yml"
    site_name: My MkDocs Material Documentation
    site_url: https://sitename.example
    theme:
        name: material
```