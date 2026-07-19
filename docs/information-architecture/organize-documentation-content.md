# Organize documentation content

Use a predictable directory structure so that readers and contributors can locate content consistently. This guide describes conventions that you can apply after you create the initial documentation site.

## Plan sections around user tasks

Group pages by the task or topic they support. Use section landing pages to describe the purpose of a group of pages and link readers to the next relevant task.

Avoid creating a directory solely because files share a format. Organize content according to the reader's information needs.

## Name files and directories

Use lowercase letters and hyphens in file and directory names. For example, use `set-up-your-project.md`, not `Set-Up-Your-Project.md` or `set_up_your_project.md`.

Use a descriptive name for each content page. Use `index.md` only for a section landing page. Keep a page's filename aligned with its title when practical; this makes generated URLs and repository paths easier to identify.

## Maintain the structure

When you add, move, or rename pages, update the navigation configuration and internal links in the same change. Build the site locally to find broken links before you commit.
