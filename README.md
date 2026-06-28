# Marketing Skills

A collection of AI agent skills for marketing tasks, built for Claude Code.

Skills are modular, self-contained packages that give Claude structured workflows, domain knowledge, and reusable scripts for specific marketing tasks.

## Skills

| Skill | Description | Requires |
|-------|-------------|----------|
| [creator-teardown](skills/creator-teardown/) | Full Instagram creator analysis pipeline - extracts posts, transcribes audio, analyzes captions and visuals, and produces four structured learnings documents | Smacient MCP, Python, ffmpeg |
| [amazon-review-insights](skills/amazon-review-insights/) | Fetches Amazon reviews for any brand and surfaces hidden patterns - silent complaints in 5-star reviews, cross-ASIN signals, competitive mentions, untapped use cases, and a customer language bank | Smacient MCP |
| [meta-ads-gap-analysis](skills/meta-ads-gap-analysis/) | End-to-end Meta Ads competitive analysis between two brands - fetches ads via Smacient, analyzes videos via Gemini, outputs 9-tab Excel report | Smacient MCP, Python, Gemini API key |
| [synth-research](skills/synth-research/) | Synthetic consumer research using SSR - runs AI persona panels against product pages or ad copy and returns PMF distributions across purchase intent, sentiment, trust, and value for money | Python, Gemini API key |

## Prerequisites

All skills require the **[Smacient Claude connector](https://smacient.com/products/marketing-context-claude/)** connected in your Claude Code session. Some skills have additional requirements - see the individual skill README for details.

## How to Use

**Install all skills at once** (global - available across all Claude Code sessions):

```bash
# macOS / Linux
cp -r skills/* ~/.claude/skills/

# Windows
xcopy /E /I skills %USERPROFILE%\.claude\skills
```

**Install a single skill** (global):

```bash
# macOS / Linux
cp -r skills/<skill-name> ~/.claude/skills/<skill-name>

# Windows
xcopy /E /I skills\<skill-name> %USERPROFILE%\.claude\skills\<skill-name>
```

**Install at project level** (available only in that workspace):

```bash
# macOS / Linux
cp -r skills/<skill-name> path/to/your/project/.claude/skills/<skill-name>

# Windows
xcopy /E /I skills\<skill-name> .claude\skills\<skill-name>
```

Once installed, Claude Code will automatically detect and trigger the skill based on your prompt. See each skill's README for trigger phrases and parameters.

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
