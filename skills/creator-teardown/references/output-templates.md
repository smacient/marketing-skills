# Output Document Templates

Templates for the four documents produced by the creator-teardown skill.
Replace all `{placeholders}` with real content derived from analysis.

---

## 1. `{slug}-script-learnings.md`

```markdown
# {Creator Name} - Script Learnings
*Derived from Whisper transcriptions of top {N} posts. {Month Year}.*

---

## Spoken Script Structure

```
[HOOK] - {describe the pattern: what the first sentence names, how stakes are set}
[SERIES OPENER] - "{exact wording if consistent}" OR describe variants observed
[SETUP] - {typical length and function}
[BODY] - {how sentences are constructed: named people? escalation? contrast?}
[TRANSITION] - "{exact phrase(s) used, verbatim}"
[PAYOFF] - {what follows the transition}
[CTA] - "{exact spoken CTA wording, verbatim}"
```

## Hook Formulas (Verbatim Examples)

List the actual spoken hook formulas observed, with real examples:
1. **{Formula name}**: "{example from transcript}"
2. **{Formula name}**: "{example from transcript}"
(continue for all observed patterns)

## Transition Phrases (Exact Words)

- "{phrase 1}" - used in {N} posts
- "{phrase 2}" - used in {N} posts

## CTA (Exact Spoken Words)

"{The exact CTA wording used at the end of videos}"

- Posts with keyword CTA: {avg comments}
- Posts without: {avg comments}

## Series Openers

"{Exact opener variant 1}"
"{Exact opener variant 2 if observed}"

## What Drives Top Performance

- #{rank} post ({views} views): {what the script did differently}
- #{rank} post ({views} views): {what the script did differently}

## What Flops

- {pattern that correlates with low views/comments}
- {pattern that correlates with low views/comments}
```

---

## 2. `{slug}-caption-learnings.md`

```markdown
# {Creator Name} - Caption Learnings
*Analysis of {N} post captions. {Month Year}.*

---

## Caption Structure

```
[HOOK LINE] - {max word count, pattern observed}
[BODY] - {line length, blank line usage, paragraph vs fragment}
[TRANSITION] - "{exact caption transition phrase(s) used}"
[CTA] - "{exact caption CTA wording}"
[SERIES TAG] - {format if used, e.g. "Day X - Series Name"}
[HASHTAGS] - {typical count, placement}
```

## Hook Line Patterns

The first line of captions (before the "more" cut):
- {pattern 1}: "{example}"
- {pattern 2}: "{example}"

## Transition Phrases (Caption vs Script)

Caption uses: "{phrase}" (different from spoken script)

## CTA Format

"{Exact caption CTA wording}"
Keyword examples observed: {list of keywords used}

## Hashtag Patterns

- Typical count: {N}
- Placement: {always at end / mixed}
- Best performing posts: {hashtag count}

## What to Never Do

- {anti-pattern from analysis}
- {anti-pattern from analysis}
```

---

## 3. `{slug}-visual-analysis.md`

```markdown
# {Creator Name} - Visual Analysis
*Frame-by-frame analysis of top {N} videos by views. {Month Year}.*

---

## Videos Analyzed

| Video | Views | Topic |
|-------|-------|-------|
| V1 | {views} | {topic} |
| V2 | {views} | {topic} |
(continue for all)

---

## Hook Frame (First 2-4 Seconds)

{Describe the hook format used most often. Is it split-screen? Full-screen image? Talking head only?}

### Formats observed:

**{Format A}** (used in V{N}, V{N}):
{Describe exactly: what fills each part of the screen, proportions, what the image shows}

**{Format B}** (used in V{N}):
{Describe}

**Rule observed:** {State the pattern - what is always/never done in the hook frame}

---

## Presenter Setup

- **Background:** {describe}
- **Outfit:** {describe}
- **Camera distance:** {medium close-up / wide / tight}
- **Camera height:** {eye level / above / below}
- **Lighting:** {describe}
- **Hands:** {visible? gestural? where positioned?}

**What is never in frame:** {list distractions or props absent}

---

## On-Screen Text System

### Style 1 - {name}
- {color, weight, position, when used}
- Examples: "{example}" / "{example}"

### Style 2 - {name}
- {color, weight, background, position, when used}
- Examples: "{example}" / "{example}"

**Captioning approach:** {keyword captions vs full continuous subtitles - frequency}

---

## B-Roll Types (in frequency order)

### 1. {Most common type}
{Describe what it looks like, when it appears, what it shows}

### 2. {Second type}
{Describe}

(continue for all observed types)

---

## Editing Rhythm

```
[0-Xs]   {what's on screen and what's happening}
[Xs-Xs]  {next segment}
[Xs-Xs]  {etc.}
[Xs-end] {CTA segment}
```

Cuts happen every {N}-{N} seconds throughout the body.
{Note any jump cuts within talking head segments}

---

## What Separates Top Posts Visually

{List 2-3 things the highest-performing videos do visually that lower ones don't}

---

## Production Checklist (to replicate)

- [ ] {item}
- [ ] {item}
- [ ] {item}
```

---

## 4. `{slug}-creator-learnings.md`

```markdown
# {Creator Name} - Creator Learnings
*Overall strategy analysis. {Month Year}.*

---

## Profile

- **Handle:** @{handle}
- **Niche:** {describe content focus}
- **Series:** {list any series they run}
- **Posting frequency:** {estimated from data}

---

## Performance Data

| Post | Views | Comments | Topic |
|------|-------|----------|-------|
| #1 | {views} | {comments} | {topic} |
| #2 | {views} | {comments} | {topic} |
| #3 | {views} | {comments} | {topic} |
(top 5-10)

---

## What Drives Views

{List the 3-5 factors most correlated with high view counts}

## What Drives Comments

{List the 3-5 factors most correlated with high comment counts - often different from views}

## Content Pillars

{What topics/angles they return to repeatedly}

## What Flops

{Topics or formats that consistently underperform}

---

## Reference Files

- Scripts: `reference/{slug}-script-learnings.md`
- Captions: `reference/{slug}-caption-learnings.md`
- Visual: `reference/{slug}-visual-analysis.md`
- Audio: `reference/{slug}/audio/`
- Videos: `reference/{slug}/videos/`
- Transcripts: `reference/{slug}/transcripts/`
```
