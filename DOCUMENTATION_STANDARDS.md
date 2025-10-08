# 📝 Documentation Standards

> **Purpose**: Ensure consistent, maintainable, and high-quality documentation across the Missing Table project.
>
> **Last Updated**: 2025-10-08

---

## 🎯 Documentation Philosophy

### Principles

1. **Clarity First** - Write for beginners, benefit experts
2. **Show, Don't Just Tell** - Include examples
3. **Keep Current** - Outdated docs are worse than no docs
4. **Make it Scannable** - Use headers, lists, tables
5. **Welcome Learners** - Remember: everyone was new once

---

## 📚 Documentation Structure

### Organization

All documentation lives in the `docs/` directory with clear organization:

```
docs/
├── README.md                      # Master hub (navigation center)
├── 01-getting-started/           # Setup and first contribution
├── 02-development/               # Daily workflows
├── 03-architecture/              # System design
├── 04-testing/                   # Testing strategy
├── 05-deployment/                # Deployment guides
├── 06-security/                  # Security practices
├── 07-operations/                # Operations and maintenance
├── 08-integrations/              # External integrations
├── 09-cicd/                      # CI/CD pipeline
└── 10-contributing/              # Contributing guides
```

---

## ✍️ Writing Standards

### Document Template

Every documentation file should follow this structure:

```markdown
# [Title]

> **Audience**: [Who should read this]
> **Prerequisites**: [What they need first]
> **Time to Complete**: [Estimated time] (optional)

Brief 1-2 sentence description of what this document covers.

---

## [Section 1]

Content...

---

## [Section 2]

Content...

---

## 📖 Related Documentation

- **[Link](path)** - Description
- **[Link](path)** - Description

---

<div align="center">

[⬆ Back to Documentation Hub](../README.md)

</div>
```

### Content Guidelines

**Headers**:
- Use emoji for visual navigation (e.g., 🎯 🚀 📚 🔧)
- Use sentence case, not title case
- Use descriptive headers that explain what's in the section

**Code Blocks**:
```bash
# Always include language identifier
# Add comments to explain what the command does
./command --flag  # Comment explaining the flag
```

**Examples**:
- Always include working examples
- Show both success and error cases
- Include expected output

**Links**:
- Use relative links: `[Link Text](../path/to/file.md)`
- Not absolute: `https://github.com/...`
- Link to related docs at the end of each file

---

## 🎨 Formatting Standards

### Markdown Conventions

**Bold**: `**Important terms**` or `**action items**`

**Italic**: `*emphasis*` or `*technical terms*`

**Code**: `` `inline code` `` for commands, variables, file names

**Lists**:
- Use `-` for unordered lists
- Use `1.` for ordered lists
- Indent with 2 spaces for nested items

**Callouts**:
```markdown
> **Note**: Informational note
> **Warning**: Important warning
> **Tip**: Helpful hint
```

**Tables**:
```markdown
| Column 1 | Column 2 |
|----------|----------|
| Value    | Value    |
```

### Difficulty Indicators

Mark content difficulty where appropriate:

- 🟢 **Beginner** - No prior knowledge needed
- 🟡 **Intermediate** - Some experience helpful
- 🔴 **Advanced** - Requires solid understanding

---

## 📝 Content Types

### Guides (How-To)

**Purpose**: Help users accomplish a specific task

**Structure**:
1. What you'll achieve
2. Prerequisites
3. Step-by-step instructions
4. Verification steps
5. Troubleshooting
6. What's next

**Example**: [First Contribution Guide](docs/01-getting-started/first-contribution.md)

### Reference Documentation

**Purpose**: Comprehensive information on a topic

**Structure**:
1. Overview
2. Detailed sections
3. API/Command reference
4. Examples
5. Related topics

**Example**: [Daily Workflow](docs/02-development/daily-workflow.md)

### Tutorials

**Purpose**: Teach concepts through hands-on practice

**Structure**:
1. Learning objectives
2. Prerequisites
3. Conceptual overview
4. Step-by-step with explanations
5. Challenges/exercises
6. Summary and next steps

**Example**: [For Students Guide](docs/10-contributing/for-students.md)

### Architecture Documentation

**Purpose**: Explain system design and decisions

**Structure**:
1. Overview with diagram
2. Key components
3. Design decisions (why)
4. Data flow
5. Trade-offs
6. Future considerations

**Example**: [Architecture Overview](docs/03-architecture/README.md)

---

## 🔄 Documentation Lifecycle

### When to Create New Documentation

**Create new docs when**:
- Adding a new feature/component
- A question is asked 3+ times
- Complex process requires explanation
- Onboarding new contributors

**Don't create new docs for**:
- Very simple, one-line answers
- Content that fits in existing docs
- Temporary changes or experiments

### Updating Documentation

**Update docs when**:
- Code changes affect workflows
- User feedback indicates confusion
- Tools or dependencies change
- Best practices evolve

**How to update**:
1. Edit the relevant file
2. Update "Last Updated" date if present
3. Check all links still work
4. Submit PR with `docs:` prefix

### Archiving Documentation

**Archive (don't delete) when**:
- Feature is removed
- Process is deprecated
- Information is outdated but historically interesting

**Archive process**:
1. Move to `docs/archive/` directory
2. Add note at top: "⚠️ This document is archived..."
3. Remove from main navigation
4. Keep for historical reference

---

## 🎓 Accessibility Guidelines

### Writing for Clarity

- Use short sentences (< 25 words)
- Use active voice ("Run the command" not "The command should be run")
- Define acronyms on first use
- Avoid jargon or explain it
- Use examples liberally

### Visual Accessibility

- Use meaningful link text (not "click here")
- Include alt text for images
- Use emoji sparingly and consistently
- Ensure code blocks have proper syntax highlighting

### International Audience

- Use simple English
- Avoid idioms and slang
- Be explicit rather than implicit
- Consider time zones (use UTC or be specific)
- Use inclusive language

---

## ✅ Documentation Checklist

Before submitting documentation:

### Content
- [ ] Clear title and overview
- [ ] Proper audience identification
- [ ] Working code examples
- [ ] Links to related documentation
- [ ] Proper difficulty indicators

### Formatting
- [ ] Follows template structure
- [ ] Consistent heading levels
- [ ] Proper code block syntax highlighting
- [ ] Tables formatted correctly
- [ ] Lists properly formatted

### Quality
- [ ] Spellchecked
- [ ] Grammar checked
- [ ] All links work
- [ ] Code examples tested
- [ ] Screenshots up-to-date (if applicable)

### Maintenance
- [ ] Includes "Last Updated" if appropriate
- [ ] Links to related docs
- [ ] Findable from main hub
- [ ] Owner identified (if applicable)

---

## 🔍 Documentation Review Process

### Self-Review

Before submitting:
1. Read it out loud - Does it make sense?
2. Follow the steps - Do they work?
3. Check from a beginner's perspective - Is anything confusing?

### Peer Review

Reviewers should check:
- [ ] Accuracy - Is the information correct?
- [ ] Completeness - Are all steps included?
- [ ] Clarity - Is it easy to understand?
- [ ] Consistency - Does it match our standards?
- [ ] Links - Do all links work?

### Approval

Documentation PRs should be approved by:
- At least one maintainer
- Subject matter expert (for technical docs)

---

## 📊 Documentation Metrics

### Health Indicators

**Good Health**:
- All docs updated within last 6 months
- < 5 broken links
- All examples work
- < 10 open documentation issues

**Needs Attention**:
- Docs over 1 year old
- > 10 broken links
- Examples don't work
- > 20 open documentation issues

### Regular Audits

**Monthly**: Check for broken links
**Quarterly**: Review most-used docs for accuracy
**Annually**: Complete documentation review

---

## 🛠️ Tools and Automation

### Recommended Tools

**Writing**:
- VS Code with Markdown extensions
- Grammarly (for grammar checking)
- Hemingway Editor (for readability)

**Link Checking**:
```bash
# Check for broken links
npx markdown-link-check docs/**/*.md
```

**Spell Checking**:
```bash
# Run spell checker
npx cspell "docs/**/*.md"
```

### CI/CD Integration

Our CI/CD pipeline automatically:
- Checks for broken links
- Validates markdown formatting
- Runs spell checker
- Checks for outdated content

---

## 📖 Examples of Good Documentation

### Internal Examples

- [Getting Started](docs/01-getting-started/README.md) - Clear, step-by-step
- [For Students](docs/10-contributing/for-students.md) - Welcoming, accessible
- [Architecture](docs/03-architecture/README.md) - Comprehensive, well-structured

### External Examples to Learn From

- [Stripe API Docs](https://stripe.com/docs/api) - Excellent API documentation
- [Vue.js Guide](https://vuejs.org/guide/) - Great tutorial structure
- [DigitalOcean Tutorials](https://www.digitalocean.com/community/tutorials) - Clear how-to guides

---

## 🙋 Questions?

### Need Help with Documentation?

- Check this standards document
- Look at example documentation
- Ask in the #documentation channel
- Tag @maintainers in your PR

### Found a Documentation Issue?

- [Open an issue](https://github.com/silverbeer/missing-table/issues/new?labels=documentation)
- Label it with `documentation`
- Be specific about what's wrong
- Suggest improvements if possible

---

## 📜 Document History

| Date | Change | Author |
|------|--------|--------|
| 2025-10-08 | Initial documentation standards created | Claude |

---

<div align="center">

**Great docs = Happy developers** 📚💚

[⬆ Back to Documentation Hub](docs/README.md)

</div>
