# GitHub Copilot Skills Migration Recommendation

## Executive Summary

This document provides recommendations for migrating the existing `.github/agents/` custom agents to the new GitHub Copilot Skills feature (`.github/skills/`). The key insight is using **skill separation** and **`allowed-tools`** to enforce workflow checkpoints architecturally rather than advisory.

---

## Skills Architecture

### Two-Phase Issue Resolution

The single `issue-resolver` agent is split into two skills to enforce the checkpoint between reproduction and fixing:

| Skill | Purpose | Key Constraint |
|-------|---------|----------------|
| `issue-reproduction` | Create tests that prove the bug exists | Cannot skip to fixing |
| `issue-fix` | Implement the fix after reproduction confirmed | Requires reproduction first |

**Workflow:**
```
User: "Fix issue #12345"
  ↓
issue-reproduction skill
  → Creates reproduction test
  → Verifies test FAILS
  → STOPS and waits
  ↓
User: "Proceed with fix"
  ↓
issue-fix skill
  → Implements fix
  → Verifies test now PASSES
  → Submits PR
```

### Bundled Resources

Skills can include skill-specific scripts and templates:

```
.github/skills/
├── issue-reproduction/
│   └── SKILL.md
├── issue-fix/
│   └── SKILL.md
├── pr-reviewer/
│   └── SKILL.md
├── sandbox-testing/
│   ├── SKILL.md
│   ├── scripts/BuildAndRunSandbox.ps1
│   └── templates/RunWithAppiumTest.template.cs
└── uitest-coding/
    ├── SKILL.md
    ├── scripts/BuildAndRunHostApp.ps1
    └── templates/
        ├── IssueTemplate.xaml.template
        ├── IssueTemplate.xaml.cs.template
        └── IssueNUnitTest.cs.template
```

### Shared Scripts

Scripts used by multiple skills remain in `.github/scripts/`:

```
.github/scripts/
├── BuildAndVerify.ps1    # Used by issue-reproduction, issue-fix, pr-reviewer
└── shared/               # Utility scripts
```

---

## Key Differences: Agents vs Skills

| Aspect | Current Agents (`.github/agents/`) | New Skills (`.github/skills/`) |
|--------|-----------------------------------|-------------------------------|
| Location | `.github/agents/*.md` | `.github/skills/<name>/SKILL.md` |
| File Name | `<name>.md` | `SKILL.md` (required name) |
| Directory | Single flat directory | Each skill in own subdirectory |
| Additional Files | Not supported | Can include scripts, resources |
| Frontmatter | `name`, `description` | Same + `license`, `allowed-tools`, `metadata` |
| Compatibility | GitHub Copilot coding agent | Copilot coding agent, VS Code, CLI |

---

## Skills Capabilities

1. **Bundled Resources**: Skills can include additional files (scripts, templates, config) in the same directory
2. **Allowed Tools**: Can restrict which tools a skill can use (enforces workflow boundaries)
3. **Metadata**: Custom key-value fields for versioning, authorship
4. **Cross-Platform**: Works in VS Code, CLI, and coding agent
---

## Relationship with Instructions Files

The `.github/instructions/` files serve a different purpose:

| Type | Purpose | Trigger |
|------|---------|---------|
| **Skills** | Complete workflows, invoked by user phrases | User says "fix issue #123" |
| **Instructions** | File-pattern contextual guidance | User edits specific files |

**Recommendation:** Keep both! They complement each other:
- Skills define **WHAT to do** (workflows, processes)
- Instructions define **HOW to do it** for specific file patterns

---

## Summary

| Recommendation | Status |
|----------------|--------|
| Split issue resolution into `issue-reproduction` + `issue-fix` | ✅ Done |
| Bundle skill-specific scripts in skill folders | ✅ Done |
| Bundle skill-specific templates in skill folders | ✅ Done |
| Keep shared scripts in `.github/scripts/` | ✅ Done |
| Keep `.github/instructions/` for file patterns | ✅ Keep |

### Final Structure

```
.github/
├── scripts/
│   ├── BuildAndVerify.ps1           # Shared
│   └── shared/                       # Utility scripts
├── skills/
│   ├── issue-reproduction/SKILL.md   # Phase 1: Create repro tests
│   ├── issue-fix/SKILL.md            # Phase 2: Implement fix
│   ├── pr-reviewer/SKILL.md          # Code review
│   ├── sandbox-testing/
│   │   ├── SKILL.md
│   │   ├── scripts/BuildAndRunSandbox.ps1
│   │   └── templates/RunWithAppiumTest.template.cs
│   └── uitest-coding/
│       ├── SKILL.md
│       ├── scripts/BuildAndRunHostApp.ps1
│       └── templates/*.template
└── instructions/                     # Keep (file-pattern guidance)
```

The migration is low-risk because:
1. The YAML frontmatter format is identical
2. The content doesn't need changes
3. Skills are the evolution of the agents concept
4. Testing can be done incrementally
