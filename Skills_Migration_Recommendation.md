# GitHub Copilot Skills Migration Recommendation

## Executive Summary

This document provides recommendations for migrating the existing `.github/agents/` custom agents to the new GitHub Copilot Skills feature (`.github/skills/`). Based on my analysis, the current agent structure is well-aligned with the Skills format, making migration straightforward.

---

## Current State Analysis

### Existing Agent Structure (`.github/agents/`)

The repository currently has 5 custom agents:

| Agent | Purpose | Trigger Phrases |
|-------|---------|-----------------|
| `issue-resolver.md` | Investigate, reproduce, and fix community-reported issues | "fix issue #XXXXX", "resolve bug #XXXXX" |
| `pr-reviewer.md` | Code review of pull requests with testing validation | "review PR #XXXXX", "code review" |
| `sandbox-agent.md` | Manual testing via Sandbox app | "test this PR", "reproduce issue" |
| `test-repro-agent.md` | Create reproduction tests only (no fixes) | "create repro for #XXXXX" |
| `uitest-coding-agent.md` | Write new UI tests | "write UI test", "add test coverage" |

### Current Format

All agents use YAML frontmatter:
```yaml
---
name: agent-name
description: Description of the agent's purpose
---
```

This format is **already compatible** with the Skills specification.

---

## Skills Feature Overview

### Key Differences: Agents vs Skills

| Aspect | Current Agents (`.github/agents/`) | New Skills (`.github/skills/`) |
|--------|-----------------------------------|-------------------------------|
| Location | `.github/agents/*.md` | `.github/skills/<name>/SKILL.md` |
| File Name | `<name>.md` | `SKILL.md` (required name) |
| Directory | Single flat directory | Each skill in own subdirectory |
| Additional Files | Not supported | Can include scripts, resources |
| Frontmatter | `name`, `description` | Same + `license`, `allowed-tools`, `metadata` |
| Compatibility | GitHub Copilot coding agent | Copilot coding agent, VS Code, CLI |

### New Skills Capabilities

1. **Bundled Resources**: Skills can include additional files (scripts, templates, config) in the same directory
2. **Allowed Tools**: Can pre-approve specific tools (e.g., `playwright`, `npm`)
3. **Metadata**: Custom key-value fields for versioning, authorship
4. **Cross-Platform**: Works in VS Code (Insiders now, stable Jan 2025), CLI, and coding agent

---

## Migration Recommendation

### Option A: Full Migration (Recommended)

Convert all agents to the Skills format:

```
.github/
├── agents/           # REMOVE (after migration)
├── skills/
│   ├── issue-resolver/
│   │   └── SKILL.md
│   ├── pr-reviewer/
│   │   └── SKILL.md
│   ├── sandbox-testing/
│   │   ├── SKILL.md
│   │   └── RunWithAppiumTest.template.cs  # Include script template
│   ├── test-reproduction/
│   │   └── SKILL.md
│   └── uitest-coding/
│       └── SKILL.md
└── instructions/     # KEEP (file-pattern based guidance)
```

**Benefits:**
- Full compatibility with all Copilot surfaces (VS Code, CLI, web)
- Ability to bundle resources (scripts, templates)
- Future-proof as Skills evolve
- Cleaner separation per skill

### Option B: Hybrid Approach

Keep agents for now, create Skills for specific use cases where bundled resources help:

```
.github/
├── agents/           # KEEP existing agents
├── skills/
│   └── sandbox-testing/
│       ├── SKILL.md
│       └── RunWithAppiumTest.template.cs
└── instructions/     # KEEP
```

**When to use:** If you want to incrementally adopt Skills while maintaining backward compatibility.

---

## Detailed Migration Steps (Option A)

### Step 1: Create Skills Directory Structure

```bash
mkdir -p .github/skills/{issue-resolver,pr-reviewer,sandbox-testing,test-reproduction,uitest-coding}
```

### Step 2: Convert Each Agent

For each agent, the content migration is straightforward since the format is nearly identical:

#### Example: issue-resolver

**Before:** `.github/agents/issue-resolver.md`
```yaml
---
name: issue-resolver
description: Specialized agent for investigating and resolving community-reported .NET MAUI issues through hands-on testing and implementation
---

# .NET MAUI Issue Resolver Agent
...
```

**After:** `.github/skills/issue-resolver/SKILL.md`
```yaml
---
name: issue-resolver
description: Specialized agent for investigating and resolving community-reported .NET MAUI issues through hands-on testing and implementation
license: MIT
metadata:
  version: "1.0"
  author: dotnet-maui-team
---

# .NET MAUI Issue Resolver Skill

## Overview
Specialized skill for investigating and resolving community-reported issues...
```

### Step 3: Add Bundled Resources (Optional)

For skills that would benefit from bundled files:

**sandbox-testing/:**
```
.github/skills/sandbox-testing/
├── SKILL.md
└── templates/
    └── RunWithAppiumTest.template.cs    # Appium test template (skill-specific)
```

**uitest-coding/:**
```
.github/skills/uitest-coding/
├── SKILL.md
└── templates/
    ├── IssueTemplate.xaml.template       # XAML page boilerplate
    ├── IssueTemplate.xaml.cs.template    # Code-behind boilerplate
    └── IssueNUnitTest.cs.template        # NUnit test boilerplate
```

**Template Organization Principle:**
- Templates used by **only one skill** → Put in that skill's `templates/` folder
- Scripts used by **multiple skills** → Keep in `.github/scripts/` (shared infrastructure)

### Step 4: Update copilot-instructions.md

Update the "Custom Agents" section to reference Skills:

```markdown
## Custom Skills

The repository includes specialized skills for specific tasks:

### Available Skills

Skills are located in `.github/skills/` and are automatically discovered by Copilot...
```

### Step 5: Remove Old Agents Directory

After verification:
```bash
rm -rf .github/agents/
```

---

## Skill-Specific Recommendations

### 1. issue-resolver → `.github/skills/issue-resolver/`

**Keep as-is content-wise.** The current workflow with checkpoints is well-designed.

**Consider adding:**
- A checklist template file for reproducible issue reporting
- Common error patterns reference

### 2. pr-reviewer → `.github/skills/pr-reviewer/`

**Keep as-is.** The code review workflow is comprehensive.

**Consider adding:**
- Review feedback template (currently inline, could be separate file)

### 3. sandbox-agent → `.github/skills/sandbox-testing/`

**Rename** for clarity (sandbox-agent → sandbox-testing).

**Bundle these resources:**
- `RunWithAppiumTest.template.cs` - Already exists in `.github/scripts/templates/`
- Validation checklist (currently embedded in instructions)

**Current reference in sandbox-agent.md:**
```markdown
1. **Read sandbox instructions**:
   - `.github/instructions/sandbox.instructions.md`
```

**After migration**, the skill becomes self-contained without needing external file reads.

### 4. test-repro-agent → `.github/skills/test-reproduction/`

**Keep as-is content-wise.**

**Consider adding:**
- Unit test template file
- UI test template files

### 5. uitest-coding-agent → `.github/skills/uitest-coding/`

**Keep as-is content-wise.**

**Consider adding:**
- XAML template
- Code-behind template
- NUnit test template
- Category reference (extracted from UITestCategories.cs programmatically)

---

## Relationship with Instructions Files

The `.github/instructions/` files serve a different purpose:

| Type | Purpose | Trigger |
|------|---------|---------|
| **Skills** | Complete workflows, invoked by user phrases | User says "fix issue #123" |
| **Instructions** | File-pattern contextual guidance | User edits `src/Controls/tests/TestCases.HostApp/**` |

**Recommendation:** Keep both! They complement each other:
- Skills define **WHAT to do** (workflows, processes)
- Instructions define **HOW to do it** for specific file patterns

Example flow:
1. User: "Write a UI test for issue #12345"
2. Copilot invokes `uitest-coding` skill (defines workflow)
3. Copilot edits `TestCases.HostApp/Issues/Issue12345.xaml`
4. `uitests.instructions.md` is automatically applied (provides file-specific conventions)

---

## Timeline Recommendation

### Phase 1: Immediate (Week 1)
1. Create `.github/skills/` directory
2. Migrate all 5 agents to skills (content unchanged)
3. Test functionality in VS Code Insiders

### Phase 2: Enhancement (Week 2-3)
1. Add bundled resources to relevant skills
2. Update `copilot-instructions.md` documentation
3. Add optional frontmatter fields (`license`, `metadata`)

### Phase 3: Cleanup (Week 4)
1. Remove `.github/agents/` directory
2. Document skill usage in README-AI.md
3. Monitor Copilot behavior and adjust

---

## Compatibility Notes

1. **VS Code Support**: Skills work in VS Code Insiders now; stable support expected January 2025
2. **Backward Compatibility**: During transition, keep both `.github/agents/` and `.github/skills/`
3. **Claude Code Compatibility**: Skills are also compatible with Claude Code (`.claude/skills/`)

---

## Summary

| Recommendation | Priority |
|----------------|----------|
| Migrate to `.github/skills/` format | ✅ Recommended |
| Keep `.github/instructions/` for file patterns | ✅ Keep |
| Add bundled resources (templates, scripts) | 🟡 Optional |
| Add metadata (version, author) | 🟡 Optional |
| Remove `.github/agents/` after migration | ⏳ After verification |

The migration is low-risk because:
1. The YAML frontmatter format is identical
2. The content doesn't need changes
3. Skills are the evolution of the agents concept
4. Testing can be done incrementally
