# Marketing Skills

A collection of AI agent skills for marketing tasks, built for Claude Code.

Skills are modular, self-contained packages that give Claude structured workflows, domain knowledge, and reusable scripts for specific marketing tasks.

## Skills

| Skill | Description |
|-------|-------------|
| [creator-teardown](skills/creator-teardown/) | Full Instagram creator analysis pipeline - extracts posts, transcribes audio, analyzes captions and visuals, and produces four structured learnings documents |

## How to Use

Install a skill globally so it is available across all Claude Code sessions:

```bash
# Copy the skill folder to your global Claude skills directory
cp -r skills/creator-teardown ~/.claude/skills/creator-teardown
```

Or install at project level (available only in that workspace):

```bash
cp -r skills/creator-teardown path/to/your/project/.claude/skills/creator-teardown
```

Once installed, Claude Code will automatically detect and trigger the skill based on your prompt.

## Structure

Each skill follows this layout:

```
skill-name/
├── SKILL.md          # Skill definition and workflow instructions
├── requirements.txt  # Python dependencies (if any)
├── scripts/          # Executable Python scripts
└── references/       # Reference files and output templates
```

## Contributing

Contributions welcome. To add a new skill, follow the structure above and open a pull request.

## License

MIT
