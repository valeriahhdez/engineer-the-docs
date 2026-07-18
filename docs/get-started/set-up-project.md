# Set up your docs-as-code project from scratch

A docs-as-code project is, at its core, a software project. The source files are Markdown, but the surrounding infrastructure (version control, dependency management, configuration, and automations) follows the same engineering practices applied to any codebase. This is what makes a documentation project maintainable, reproducible, and deployable by a CI/CD pipeline.

This tutorial walks you through setting up a documentation site from scratch using Zensical as the static site generator (SSG). [Zensical](https://zensical.org) is the successor project to Material for MkDocs, built by the same team.

To learn more about why choosing Zensical is the right move at this time, see the [Zensical Monthly, February 2026 Newsletter](https://mail.zensical.org/monthly/2026/02/index.html) and the [roadmap](https://zensical.org/about/roadmap/).  

By the end, you will have the following:

- A Git repository connected to GitHub.
- A reproducible Python virtual environment with pinned dependencies.
- A `zensical.toml` configuration file with the settings that matter.
- A folder structure that scales and follows conventions.
- A locally running site you've verified before committing.

The project you build here is the foundation for adding GitHub Actions to build and deploy your pipeline automatically on every push.

???note "Zensical is under active development"
      Zensical is a young project and its configuration schema may evolve between
      releases. Before following this tutorial, cross-reference the
      [official Zensical documentation](https://zensical.org/docs/) to confirm
      that configuration keys and CLI commands reflect the current version.
      This tutorial is written against Zensical 0.0.43.

## Prerequisites

Before you begin, make sure you have the following:

- **Git** installed on your system ([download](https://git-scm.com/downloads))
- **A GitHub account** ([github.com](https://github.com))
- **Python 3.8 or later** installed ([download](https://www.python.org/downloads/))
- A terminal (macOS/Linux) or Command Prompt / PowerShell (Windows)

## Step 1: Initialize your Git repo and connect it to GitHub

### a. Create your project folder and initialize Git

Open a terminal or command prompt and run this command:

```bash title="git_init", linenums="1"
mkdir YOUR_PROJECT_NAME
cd YOUR_PROJECT_NAME
git init
```

`git init` creates a hidden `.git` directory that tracks your project's history. Your project folder is now a local Git repository.

### b. Create a `.gitignore`

Not everything in your project folder should be committed. The virtual environment, the built site output, and Python cache files are all generated artifacts that can be recreated from what's already in the repo. Committing them adds noise without value.

Create a `.gitignore` file in the project root and paste following content into it:

```title=".gitignore", linenums="1"
# Virtual environment
.venv/

# Zensical build output
site/

# Python cache
__pycache__/
*.pyc
```

### c. Create the GitHub repository and set the remote

Create an empty repository, no README, no license, no `.gitignore` file.

1. Go to [github.com/new](https://github.com/new)
2. Give the repository the same name as your local folder (`YOUR_PROJECT_NAME`).
3. Leave the **Add README** toggle off. 
4. Select **No .gitignore** and **No license** options from the dropdown menus. 
5. Click **Create repository**

GitHub shows you a set of setup commands. Return to your terminal and copy and paste the commands under **push an existing repository from the command line**:

```bash title="push existing repository"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_PROJECT_NAME.git
git branch -M main
```

## Step 2. Set up your Python environment and pin your dependencies

### Why a virtual environment matters

A Python virtual environment is an isolated workspace that allows you to install project-specific dependencies without altering your global system Python. By separating your project's libraries from other applications on your machine, it prevents package version conflicts and ensures reproducible builds. Combined with a `requirements.txt` that pins exact versions, a virtual environment  guarantees that every machine running this project, including a GitHub Actions runner,  installs the same dependencies.

For a deeper dive into managing environments, see the [Real Python Guide to Virtual Environments](https://realpython.com/python-virtual-environments-a-primer/).

### a. Create and activate the virtual environment

=== "macOS / Linux"

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate # Activation command
    ```

=== "Windows"

    ```cmd
    python -m venv .venv
    .venv\Scripts\activate # Activation command
    ```
   
Your prompt changes to show `(.venv)`, indicating the environment is
active. From this point on, any Python package installation goes into `.venv`, not your global system Python.

??? tip "Create a shortcut for your environment"
    To avoid typing the full activation command every time you want to jump back into your project, you can create a shortcut. A shell alias in your `.zshrc` or `.bashrc` (macOS/Linux), or a function in your PowerShell profile (Windows).  Search for "shell alias" (macOS/Linux) or "PowerShell profile function" (Windows) to get started.

### b. Install Zensical

```bash
pip install zensical
```

This installs Zensical and all of its dependencies into your virtual
environment.

???note "Run `pip install` within your environment"
    Make sure your terminal shows the `(.venv)` prefix before running `pip install`. If you install packages without activating the environment, your system may fail to register the zensical command line tools.

### c. Pin your dependencies

```bash
pip freeze > requirements.txt
```

`pip freeze` outputs every package currently installed in your environment,
along with its exact version number. Writing that output to `requirements.txt`
creates a [reproducibility contract](https://medium.com/@shihabyahia22/why-is-requirements-txt-so-important-for-programmer-ead437b4b6ca): anyone (or any machine) that runs
`pip install -r requirements.txt` will get the same environment you have right
now.

Open `requirements.txt` and confirm it exists and contains `zensical==` with a
version number. It will also include Zensical's transitive dependencies.

???tip "When to update `requirements.txt`"
    Re-run `pip freeze > requirements.txt` any time you install or upgrade a
    package. Keeping it in sync with your actual environment is what makes it
    useful. In the next tutorial, your GitHub Actions workflow will use this
    file to install dependencies on the CI runner.

## Step 3: Bootstrap and configure your site

### a. Bootstrap the project structure

Zensical includes a `new` command that generates a project scaffold for you:

```bash
zensical new .
```

This creates the following structure in your project folder:

```
.
├─ .github/workflows
│  └─ docs.yml          # A starter GitHub Actions workflow
├─ docs/
│  ├─ index.md          # Your home page
│  └─ markdown.md       # A Markdown reference page
└─ zensical.toml        # Your site configuration
```

The `.github/workflows/docs.yml` file is a useful reference, but you'll write
your own workflow from scratch in the next tutorial so you understand every
line of it.

### b. Configure `zensical.toml`

Open `zensical.toml`. This is where Zensical reads everything it needs to know
about your site: its identity, its structure, its appearance, and which features
to enable.

All settings live inside a `[project]` scope. Here's a configuration that's
appropriate for a professional documentation site, with explanations of each
decision:

```toml
[project]
site_name = "Engineer the Docs"
site_url = "https://YOUR-USERNAME.github.io/engineer-the-docs/"
site_description = "A docs-as-code portfolio site built with Zensical."
site_author = "Your Name"
docs_dir = "docs"

nav = [
  {"Home" = "index.md"}
]
```

#### Why `site_url` is not optional

Setting `site_url` is technically optional, but skipping it disables several
features you want: instant navigation, instant previews, and correctly generated
sitemaps. If you're deploying to GitHub Pages, Zensical needs
this value to generate correct internal links. Set it now, even if the site
isn't live yet.

#### Why navigation should be explicit

By default, Zensical infers navigation from the folder structure. Define nav explicitly in zensical.toml to specify which pages appear in the navigation, their order, and their labels. This lets you organize navigation according to your information architecture instead of relying on the file system.

#### Theme configuration

Zensical ships with two theme variants: `modern` (the default) and `classic`,
which matches Material for MkDocs exactly. For a new project, use the default `modern`. You can also enable navigation features that improve usability
on a multi-section site:

```toml
[project.theme]
features = [
    "navigation.instant",
    "navigation.instant.progress",
    "navigation.tabs",
    "navigation.path",
    "toc.follow"
]
```

The following list briefly explains each configuration feature:

- `navigation.instant`: Turns the site into a single-page application.
  Internal links load without a full page reload, which makes the site faster.
- `navigation.instant.progress`: Shows a progress indicator during navigation
  on slower connections.
- `navigation.tabs`: Renders top-level nav sections as a tab bar below the
  header, which works well for a multi-section documentation site.
- `navigation.path`: Adds breadcrumb navigation above each page title, helping
  readers understand where they are in the structure.
- `toc.follow`: Keeps the table of contents sidebar scrolled to the active
  section as the reader moves down the page.

## Step 4: Establish your folder structure

The scaffold created by `zensical new` gives you a `docs/` directory with two
files. Before adding more content, establish clear file-naming and directory conventions. Establishing and documenting these standards early ensures a predictable file structure that supports automated CI pipelines and multi-author collaboration.

### Recommended structure for a docs engineering site

```
engineer-the-docs/
├─ .github/
│  └─ workflows/
│     └─ docs.yml
├─ .venv/                    # In .gitignore, not committed
├─ docs/
│  ├─ index.md               # Site home page
│  ├─ introduction/
│  │  └─ index.md
│  ├─ set-up-your-project/
│  │  └─ index.md            # This article
│  └─ assets/
│     └─ images/
├─ .gitignore
├─ requirements.txt
└─ zensical.toml
```

### Recommended file naming conventions

Consider adopting the following naming conventions for your project:

- Lowercase only: file and folder names should never contain uppercase
  letters. `Set-Up-Your-Project.md` becomes `set-up-your-project.md`.
- Hyphens, not underscores: `set-up-your-project`, not
  `set_up_your_project`. Hyphens are standard in URLs and easier to read.
- Descriptive names: the file name should tell you what the page covers
  without opening it. `index.md` is fine for section landing pages; everything
  else should be named for its content.
- `index.md` for section landing pages: when a folder represents a section
  of your site, create an `index.md` inside it. Zensical treats this as the
  section's landing page.

These conventions matter beyond aesthetics. When your GitHub Actions workflow
references file paths, and when Zensical generates URLs from them, consistency
prevents broken links and unpredictable build behavior.

## Step 5: Run locally and verify before you commit

Run the site locally before committing to find configuration and link errors earlier.

### a. Start the local preview server

```bash
zensical serve
```

Open [localhost:8000](http://localhost:8000) in your browser. Zensical starts a
local web server and rebuilds the site automatically whenever you save a file.

### b. Verify the site works as expected

Before making your first commit, confirm the following:

- The site loads: the home page renders without errors.
- Navigation appears correctly: the pages defined in your `nav` are
  visible and link to the right content.
- No build warnings in the terminal: Zensical outputs warnings for missing
  pages, broken internal links, and configuration issues; treat them as errors
  at this stage.
- The page title matches `site_name`: confirms your `zensical.toml` is
  being read correctly

If you see configuration warnings, fix them before committing. A clean build
locally is a prerequisite for a clean build on CI.

### c. Make your first commit

After you verify the site is running cleanly, stop the server (`Ctrl+C`) and commit
everything:

```bash
git add .
git commit -m "Initial project setup: Zensical, venv, config, folder structure"
git push -u origin main
```

A meaningful commit message matters here too. `Initial commit` tells a future
reader nothing. The message above tells
them exactly what this commit changes.

## What's next

You now have a version-controlled, reproducible Zensical project that runs
locally and is pushed to GitHub. Every structural decision you made in this
tutorial — the virtual environment, the pinned `requirements.txt`, the explicit
nav in `zensical.toml`, the consistent folder structure — was made with one
purpose beyond the immediate one: to make this project automatable.

Right now, publishing your site requires you to run `zensical build` and deploy
the output manually. The next tutorial removes that manual step entirely. You'll
write a GitHub Actions workflow that triggers on every push to `main`, installs
your dependencies from `requirements.txt`, builds the site, and deploys it to
GitHub Pages automatically.

→ [Automate your pipeline with GitHub Actions](#) 