---
title : "Set up a docs-as-code project with Zensical"
---

# Set up a docs-as-code project with Zensical

A docs-as-code project uses source files, version control, dependency management, configuration, and automation in the same way as a software project. This tutorial uses Markdown source files and Zensical to create a documentation site.

This tutorial shows you how to set up a documentation site using [Zensical](https://zensical.org), a static site generator (SSG). Zensical is the successor project to Material for MkDocs and is built by the same team.

For information about Zensical's development plans, see the [roadmap](https://zensical.org/about/roadmap/).

By the end, you will have the following:

- A local Git repository connected to GitHub.
- A reproducible Python virtual environment with pinned dependencies.
- A `zensical.toml` configuration file with basic settings.
- A consistent folder structure.
- A locally running site that you have verified before committing.

The next tutorial uses this project to build and deploy the site with GitHub Actions.

???note "Zensical is under active development"
      Zensical is a young project and its configuration schema may evolve between
      releases. Before following this tutorial, cross-reference the
      [official Zensical documentation](https://zensical.org/docs/) to confirm
      that configuration keys and CLI commands reflect the current version.
      This tutorial is written against Zensical 0.0.43.

## Before you begin

Before you begin, make sure you have the following:

- [Git](https://git-scm.com/downloads) installed on your system.
- A [GitHub account](https://github.com).
- The Python version supported by your target Zensical release. Check the [Zensical installation documentation](https://zensical.org/docs/) for the current requirement.
- A terminal on macOS or Linux, or Command Prompt or PowerShell on Windows.
- Permission to create a GitHub repository.

Verify the installed tools:

```bash
git --version
python --version
```

On macOS or Linux, use `python3 --version` if `python` is unavailable.

## 1. Initialize a Git repository and connect it to GitHub

### a. Create a project folder and initialize Git

Open a terminal or command prompt and run this command:

```bash title="git_init", linenums="1"
mkdir YOUR_PROJECT_NAME
cd YOUR_PROJECT_NAME
git init
```

`git init` creates a hidden `.git` directory. Your project folder is now a local Git repository.

### b. Create a `.gitignore` file

Do not commit generated files that can be recreated from the project source. These include the virtual environment, built site output, and Python cache files.

Create a `.gitignore` file in the project root and add the following content:

```title=".gitignore", linenums="1"
# Virtual environment
.venv/

# Zensical build output
site/

# Python cache
__pycache__/
*.pyc

# Local project caches
.cache
*.cache/
```

### c. Create a GitHub repository and set the remote

Create an empty GitHub repository. Do not add a README, license, or `.gitignore` file; your local project already contains the files required for this tutorial.

1. Go to [github.com/new](https://github.com/new).
2. Give the repository the same name as your local folder (`YOUR_PROJECT_NAME`).
3. Leave the **Add README** toggle off.
4. Select **No .gitignore** and **No license** from the dropdown menus.
5. Click **Create repository**.

GitHub displays setup commands. Run the following commands, replacing the placeholders with your GitHub user name and project name:

```bash title="push existing repository"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_PROJECT_NAME.git
git branch -M main # Creates the git branch main
```

If Git prompts for a user name or email when you commit later, configure your Git identity. For instructions, see [Set Git username](https://docs.github.com/en/get-started/git-basics/setting-your-username-in-git) and [Set Git email](https://docs.github.com/en/account-and-profile/how-tos/setting-up-and-managing-your-personal-account-on-github/managing-email-preferences/setting-your-commit-email-address).

## 2. Create a Python virtual environment and pin dependencies

A Python virtual environment isolates project dependencies from the system Python installation. For more information, see the [Python `venv` documentation](https://docs.python.org/3/library/venv.html).

A `requirements.txt` file records the installed package versions so another environment can install the same set of dependencies.

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
   
Every time you activate the environment, your prompt changes to show `(.venv)`. From this point forward, any Python package should be installed inside `.venv`, not your global system Python.

### b. Install Zensical

```bash
python -m pip install zensical
```

This installs Zensical and all of its dependencies into your virtual
environment.

???note "Run commands in the virtual environment"
    Activate `.venv` before installing packages or running Zensical commands. If `zensical` is not found after installation, confirm that the environment is active and run `python -m pip show zensical`.

### c. Pin dependencies

```bash
python -m pip freeze > requirements.txt
```

`pip freeze` outputs every package currently installed in your environment,
along with its exact version number. Writing that output to `requirements.txt`
records the environment in `requirements.txt`. A machine can install these versions by running `python -m pip install -r requirements.txt`.

Open `requirements.txt` and confirm it exists and contains `zensical==` with a
version number. It will also include Zensical's transitive dependencies.

???tip "Update `requirements.txt` after dependency changes"
    Run `python -m pip freeze > requirements.txt` after you install or upgrade a package. The GitHub Actions workflow in the next tutorial uses this file to install dependencies.

## 3. Create and configure a Zensical site

### a. Create the project structure

Zensical includes a `new` command that generates a project scaffold:

```bash
zensical new .
```

The command might prompt before creating files in a nonempty directory. Review the prompt and keep the `.gitignore` and `requirements.txt` files you created. The generated project includes the following files:

```text
.
├─ .github/workflows
│  └─ docs.yml          # A starter GitHub Actions workflow
├─ docs/
│  ├─ index.md          # Your home page
│  └─ markdown.md       # A Markdown reference page
└─ zensical.toml        # Your site configuration
```

The generated `.github/workflows/docs.yml` file is not required for this tutorial. The next tutorial explains how to create and configure a workflow.

### b. Configure `zensical.toml`

Open `zensical.toml`. This file specifies the site's identity, structure, appearance, and enabled features.

Add or update the following settings in the `[project]` section. Replace the placeholders before you deploy the site:

```toml
[project]
site_name = "YOUR_SITE_NAME"
site_url = "https://YOUR-USERNAME.github.io/YOUR_PROJECT_NAME/"
site_description = "A docs-as-code portfolio site built with Zensical."
site_author = "Your Name"
docs_dir = "docs"

nav = [
  {"Home" = "index.md"}
]
```

#### The `site_url` setting

Set `site_url` to the URL where you plan to publish the site. For a GitHub Pages project site, the URL typically follows this pattern: `https://YOUR-USERNAME.github.io/YOUR_PROJECT_NAME/`. Check the [Zensical documentation](https://zensical.org/docs/setup/basics/) for the effects of omitting this setting in your target release.

#### Explicit navigation

By default, Zensical infers navigation from the folder structure. Define `nav` explicitly in `zensical.toml` to specify which pages appear in the navigation, their order, and their labels. This lets you organize navigation according to your information architecture instead of relying on the file system.

#### Theme configuration

Zensical provides the `modern` theme by default and a `classic` variant for Material for MkDocs compatibility. The following configuration enables optional navigation features:

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

The following list describes the configured features:

- `navigation.instant`: Loads internal links without a full page reload.
- `navigation.instant.progress`: Shows a progress indicator during navigation
  on slower connections.
- `navigation.tabs`: Renders top-level navigation sections as tabs below the header.
- `navigation.path`: Adds breadcrumb navigation above each page title.
- `toc.follow`: Keeps the table of contents aligned with the active section.

For a feature reference and theme-selection guidance, see the [Zensical documentation](https://zensical.org/docs/setup/basics/). Use only features supported by the Zensical version recorded in `requirements.txt`.

## 4. Create a documentation project structure

The scaffold created by `zensical new` includes a `docs/` directory. Use a consistent structure before you add more content.

### Project structure

```text
engineer-the-docs/
├─ .github/
│  └─ workflows/
│     └─ docs.yml
├─ .venv/                    # In .gitignore, not committed
├─ docs/
│  ├─ index.md               # Site home page
│  ├─ introduction/
│  │  └─ index.md            # Section landing page
│  ├─ get-started/
│  │  ├─ set-up-your-project # This article
│  │  └─ index.md            # Section landing page
│  └─ assets/
│     └─ images/
├─ .gitignore
├─ requirements.txt
└─ zensical.toml
```

### File naming conventions

Consider using the following conventions:

- Use lowercase letters: `set-up-your-project.md`, not `Set-Up-Your-Project.md`.
- Use hyphens between words: `set-up-your-project`, not `set_up_your_project`.
- Use descriptive names for content pages. 
- Use `index.md` for a section landing page.

For guidance about planning sections, naming content, and maintaining the structure, see Organize documentation content. This information is separate from the setup procedure so that you can apply it as the site grows.

## 5. Preview and verify the documentation site locally

Run and build the site locally before committing. This identifies configuration and link errors before the CI workflow runs.

### a. Start the local preview server

```bash
zensical serve
```

Open [localhost:8000](http://localhost:8000) in your browser. Zensical starts a local web server and rebuilds the site when you save a file.

### b. Verify the site

Before making your first commit, confirm the following:

- The home page renders without errors.
- The pages defined in `nav` are visible and link to the intended content.
- The page title matches `site_name`.
- The terminal does not show warnings or errors.

Stop the server with `Cmd+C`(MacOS) `Ctrl+C` (Windows), then build the site:

```bash
zensical build
```

Fix warnings and errors before committing. If port 8000 is already in use, stop the process using that port or specify an available port according to the Zensical CLI documentation.

## 6. Make the first commit

Commit the project files:

```bash
git add .
git commit -m "Initial project setup: Zensical, venv, config, folder structure"
git push -u origin main
```

If `git push` requests authentication, follow GitHub's instructions for authenticating over HTTPS or SSH.

## What's next

You now have a Zensical project that runs locally and is stored in GitHub. The project includes a virtual environment, recorded Python dependencies, explicit navigation, and a consistent file structure.

The next tutorial adds a GitHub Actions workflow that installs dependencies, builds the site, and deploys it to GitHub Pages when you push changes to `main`.

Continue to: _Automate your pipeline with GitHub Actions_. 
