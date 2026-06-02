# ApplyKit — PR/FAQ

---

## PRESS RELEASE

**ApplyKit: A Job Search Pipeline That Works While You Sleep and Delivers Ready-to-Apply Materials by Morning**

*June 2026*

Today, Jeff Watson released ApplyKit, an automated job search pipeline that monitors company career pages overnight, evaluates new postings against the user's profile, ranks them by fit, and generates tailored application materials — all before the user wakes up. By morning, the user reviews a ranked list of opportunities, each with a pre-built resume and cover letter, and applies at the push of a button.

Job searching is a pipeline problem disguised as a writing problem. The bottleneck isn't crafting a good resume. It's the hours spent finding postings, reading each one, deciding which are worth pursuing, and then tailoring materials for each. Most professionals either apply with a generic resume (fast but low quality) or customize each one (high quality but unsustainable). ApplyKit eliminates the tradeoff by automating the entire pipeline from discovery through document generation.

ApplyKit runs five named steps:

**1. Scout** — Monitor target companies' career pages on a schedule. When a new posting appears, ingest the job description automatically. Users can also feed in JDs manually — by URL, file, or pasted text — for ad-hoc evaluation anytime.

**2. Score** — Evaluate each JD against the user's profile across 10 weighted dimensions: Role Fit, Technical Match, Leadership Match, Mission Alignment, Growth Potential, Compensation Signal, Location/Remote, Security Domain, Government Adjacency, and Culture Signal. Each dimension produces a score (0-100) with a written explanation of why it scored the way it did. The dimensions and weights are fully configurable.

**3. Rank** — Sort all scored opportunities by weighted total. Assign letter grades (A through F) and recommendations: A/B+ roles get "Apply immediately," B roles get "Strong candidate," C roles get "Consider if aligned with goals," and D/F roles get "Skip." The ranked list accumulates over time, giving the user a living view of their best options.

**4. Craft** — For every role that scores above the user's threshold, automatically generate a customized resume and cover letter. The resume is built by surgically editing the user's base resume XML to align with the JD's language and requirements. The cover letter is written in the user's authentic voice. Both are rendered as .docx and .pdf files, ready to submit.

**5. Apply** — The user reviews the morning's results: a ranked list with grades, dimension breakdowns, and pre-built materials for each qualifying role. For any role they want to pursue, the materials are already done. Review, approve, submit. The tracker logs each application's status and maintains a pipeline view across all active opportunities.

"I used to spend my evenings reading job postings and my weekends customizing resumes. Now I spend 10 minutes over coffee reviewing what ApplyKit found overnight. The roles are scored, the materials are ready, and I just decide yes or no," said Watson.

ApplyKit includes three mechanisms to prevent runaway volume and improve over time:

**Volume caps.** Three configurable knobs prevent the pipeline from generating more than the user can review. A *score cap* limits how many JDs get evaluated per run (default 25, prioritized by company tier). A *craft threshold* sets the minimum grade for automatic material generation (default B+/85). A *craft cap* limits how many resumes and cover letters are built per run (default 5 — the top-scoring roles win the slots). All three are configurable per company, so dream employers can have lower thresholds.

**Feedback loop.** When the user reviews the morning's results, they can agree (proceed to apply), skip (not now), or disagree with a reason ("this is really an IC role," "compensation is too low," "I don't want adtech"). Disagreements are logged with the dimension scores and the user's reason. After repeated patterns emerge — for example, rejecting four roles where Compensation Signal scored below 60 — ApplyKit suggests weight adjustments: "You've consistently rejected roles with low compensation scores. Want to increase Compensation weight from 10% to 15%?" Disagreement examples also feed into the evaluation prompt as few-shot calibration, so the scorer learns from specific past mistakes.

**Outcome tracking.** The tracker logs every status transition: applied, got an interview, received an offer, rejected. Over time, this creates a dataset correlating dimension scores with real outcomes. Which dimensions actually predicted interviews? If high Mission Alignment consistently leads to callbacks but Technical Match doesn't, that's a signal to reweight. The data collection starts from day one; the analytics layer is a future feature that reads what's already being captured.

ApplyKit is built for modularity. The five steps are independent components with clean interfaces. New job sources plug into Scout without touching Score. New evaluation criteria plug into Score without touching Craft. The scheduled pipeline and the ad-hoc CLI share the same engine. Power users can run any step independently from the command line: `applykit scout`, `applykit score <jd>`, `applykit rank`, `applykit craft <id>`, or `applykit status`.

ApplyKit is available at github.com/jeff-watson/applykit as a private repository. It requires Python 3.10+ and runs primarily as a scheduled Cowork task, with an optional standalone CLI for power users.

---

## THE 10 SCORING DIMENSIONS

Each JD is evaluated across these 10 dimensions. Weights are configurable — the defaults below reflect a profile optimizing for AI/security leadership roles, but any user can adjust them for their own priorities.

### 1. Role Fit (20%)
Does the title, scope, and day-to-day match what the user is looking for? A "Senior Engineer" posting scored against a Director-level profile would lose points here. Evaluates seniority alignment, functional match, and whether the role description reflects real responsibilities or is a repackaged IC role with a leadership title.

### 2. Technical Match (15%)
How much does the required tech stack overlap with the user's experience? Evaluates programming languages, frameworks, cloud platforms, and domain-specific tools. Distinguishes between "nice to have" and "required" qualifications. A Python/AWS role scores high for a Python/AWS user even if it also lists Go.

### 3. Leadership Match (15%)
Does the management scope match? Evaluates team size expectations, org scope, cross-functional coordination, and whether the role is people management, technical leadership, or both. A role expecting 50 direct reports scores differently than one with 5.

### 4. Mission Alignment (10%)
Does the company's mission resonate with the user's values and interests? Evaluates stated mission, industry sector, and whether the work contributes to something the user cares about. Configurable — a user passionate about AI safety would weight this differently than someone optimizing purely for compensation.

### 5. Growth Potential (10%)
What's the career trajectory from this role? Evaluates whether the position is a step up, lateral, or step down. Looks for signals about learning opportunities, exposure to new domains, promotion paths, and whether the role leads somewhere or is a dead end.

### 6. Compensation Signal (10%)
What do the salary signals suggest? Many JDs don't list compensation, but they contain signals: level, title, location, company stage, and industry. When ranges are listed, they're compared directly to the user's target. When they aren't, the evaluator infers a likely range and flags confidence level.

### 7. Location/Remote (5%)
Does the location model work? Evaluates remote, hybrid, or on-site requirements against the user's preferences. A fully remote role scores high for a remote-preferring user. A role requiring relocation to a non-target city scores low. Hybrid arrangements are evaluated based on commute feasibility.

### 8. Security Domain (5%)
How relevant is the role to cybersecurity, AI safety, or trust and safety? For users with security backgrounds, this dimension captures domain relevance that Role Fit alone misses. A PM role at a security company scores differently than a PM role at a social media company.

### 9. Government Adjacency (5%)
Does the role connect to public sector, defense, or intelligence work? Evaluates whether security clearance is valued, whether the company has government contracts, and whether the user's military or government experience is an asset. Relevant for users with clearances or public sector backgrounds.

### 10. Culture Signal (5%)
What does the JD's language suggest about team culture? Evaluates tone, values language, work-life signals, and red flags. "Fast-paced environment" reads differently than "sustainable pace." "Wear many hats" suggests under-resourcing. This dimension is inherently subjective and the evaluator explains its reasoning.

---

## FREQUENTLY ASKED QUESTIONS

### Customer (User) FAQs

**Q: What do I actually see when I wake up?**

A ranked list of new job postings that appeared overnight on your monitored companies' career pages. Each posting has a letter grade, a per-dimension score breakdown, and — for roles above your threshold — a tailored resume and cover letter already generated. You review the list, tap "apply" on the ones you like, and the materials are ready to attach.

**Q: How do I add companies to monitor?**

Add them to your Scout configuration — a YAML file listing company names and career page URLs. ApplyKit checks each one on the schedule you set (daily, twice daily, weekly). When a new posting appears that wasn't there before, it enters the pipeline automatically.

**Q: What if I find a role myself and want to evaluate it right now?**

That's the ad-hoc mode. Run `applykit score <url>` or paste the JD text. It scores immediately using the same 10 dimensions. If you like the result, run `applykit craft <id>` to generate materials. Same pipeline, just triggered manually instead of on a schedule.

**Q: Can I adjust which roles get automatic materials?**

Yes. Your threshold is configurable — by default, any role scoring B+ (85+) gets materials generated automatically during the overnight run. You can raise it (only A-grade roles) or lower it (anything C+ and above). You can also set per-company thresholds if you want to be more aggressive about certain employers.

**Q: How accurate is the scoring?**

The scoring externalizes the same judgment you'd apply reading a JD carefully. In testing, the evaluator agreed with the user's own assessment roughly 85% of the time. The dimension breakdown is where the real value lives — it shows *why* a role scored the way it did. An A overall with an F on Compensation Signal tells you something specific. You can always override the recommendation.

**Q: What does ApplyKit do with my data?**

Everything stays local. Your profile, accomplishments, and application history live on your machine. JD text is sent to Claude for scoring during the evaluation step — nothing else is transmitted. No telemetry, no analytics, no cloud storage.

**Q: Can I customize the scoring dimensions?**

Fully. The 10 defaults are a starting point. You can change weights, rename dimensions, add new ones, or remove ones that don't apply to your search. Everything is in a YAML config file. A product designer might drop "Security Domain" and "Government Adjacency" in favor of "Design Craft" and "Portfolio Fit."

**Q: What if I disagree with a recommendation?**

Flag it. During your morning review, mark any role you disagree with and say why — "this is really an IC role despite the title," "compensation is too low for DC," "I don't want to work in adtech." ApplyKit logs your disagreement alongside the dimension scores. After it sees a pattern — say you've rejected four roles where Compensation Signal scored below 60 — it suggests a weight adjustment: "Increase Compensation weight from 10% to 15%?" You approve or decline. Over time, the scoring aligns with your actual preferences, not just your stated ones.

**Q: Won't this generate too many applications overnight?**

No. Three caps prevent runaway volume. First, a score cap limits how many JDs get evaluated per run (default 25). Second, a craft threshold sets the minimum grade for material generation (default B+). Third, a craft cap limits materials per run (default 5) — even if 12 roles score A, only the top 5 get resumes and cover letters built. You configure all three in YAML, and you can set different thresholds per company.

**Q: Does the scoring get better over time?**

Yes, through two mechanisms. First, your disagreements feed back into the evaluation prompt as calibration examples — "the user rejected Role X at Company Y despite an A grade because [reason]." This teaches the scorer to catch patterns it missed. Second, outcome tracking correlates dimension scores with real results (did this application lead to an interview? an offer?). Over time, you discover which dimensions actually predict success in your search, and can reweight accordingly.

**Q: Does this work with the CLI?**

Yes. Power users can run any step independently: `applykit scout` checks career pages, `applykit score <jd>` evaluates a single JD, `applykit rank` shows the current leaderboard, `applykit craft <id>` generates materials, `applykit status` shows the pipeline. The scheduled mode and the CLI share the same engine.

---

### Internal (Builder) FAQs

**Q: How does the overnight scheduled run work?**

ApplyKit uses Cowork's scheduled task infrastructure. A task runs on a cron schedule (e.g., daily at 5 AM). It executes the Scout → Score → Rank → Craft pipeline end-to-end. Scout checks career pages and diffs against a local cache. New postings enter Score. Results feed Rank. Roles above threshold enter Craft. When the user opens Cowork in the morning, the results are waiting.

**Q: Why scheduled-first instead of on-demand?**

The highest-value version of this tool does work *before* the user asks. On-demand evaluation is reactive — you find a JD, then decide if it's worth customizing. Scheduled evaluation is proactive — opportunities find you, pre-scored and pre-packaged. Ad-hoc mode exists for roles the user discovers outside the monitored channels, but the default experience should be "wake up to a curated inbox."

**Q: How does Scout detect new postings vs ones it already processed?**

Scout maintains a local SQLite cache of previously seen postings (URL + title hash). Each run fetches the career page, extracts job listings, and diffs against the cache. New entries enter the pipeline. Previously seen entries are skipped. The cache persists across runs.

**Q: How does this differ from the resume-customizer skill?**

The resume-customizer is a document generation engine — it takes a JD and produces a tailored resume and cover letter. ApplyKit is the orchestration layer above it. ApplyKit decides *which* JDs deserve materials, *when* to generate them, and *how* to present the results. The Craft step calls the resume-customizer under the hood. Each can evolve independently.

**Q: Why not use job board APIs (Indeed, LinkedIn)?**

Most job board APIs are paywalled, rate-limited, or terms-of-service hostile to automated access. Career pages are public, stable, and company-controlled. Starting with direct career page monitoring is simpler, cheaper, and more reliable. Job board integrations can be added later as a new Scout source without changing the rest of the pipeline.

**Q: What's the cost per overnight run?**

Inside Cowork's scheduled tasks: included in the Cowork subscription. Each JD evaluation is one Claude call — roughly $0.01-0.02 standalone. A night that surfaces 10 new postings costs about $0.15 in API calls if running standalone. Resume and cover letter generation is additional processing time but uses the same Claude session.

**Q: What if a career page changes format?**

Scout uses an LLM-assisted extraction step — it sends the page HTML to Claude and asks it to extract job listing titles and URLs. This is more resilient to format changes than brittle CSS selectors. If a page fundamentally restructures, the extraction prompt may need adjustment, but minor redesigns are handled automatically.

**Q: How does the feedback loop work technically?**

Three components. First, a `feedback` table in SQLite stores each disagreement: application ID, dimension scores at time of evaluation, user's verdict (agree/disagree/skip), user's reason (free text), and timestamp. Second, a calibration module runs periodically (or on demand via `applykit calibrate`) that analyzes disagreement patterns — grouping by dimension, identifying thresholds the user consistently rejects below, and generating weight adjustment suggestions. Third, the evaluation prompt itself includes the N most recent disagreement examples as few-shot calibration context, so the LLM sees concrete cases of "you scored this high but the user rejected it because X." The calibration suggestions are always presented to the user for approval — the system never auto-adjusts weights.

**Q: How does outcome tracking feed into scoring?**

The tracker already logs status transitions (APPLYING → INTERVIEWING → OFFERED → ACCEPTED/REJECTED). The analytics layer (Future F2) reads this data and correlates dimension scores with outcomes. For example: "Roles where Mission Alignment scored above 80 led to interviews 60% of the time, vs 20% for roles below 80." This surfaces which dimensions are actually predictive for this specific user's job search. The insight is presented as a suggestion — "Mission Alignment appears to be your strongest predictor. Consider increasing its weight." The user decides whether to act on it.

**Q: What prevents the feedback loop from overfitting?**

Two guardrails. First, weight adjustments are suggested, never automatic — the user approves every change. Second, the calibration module requires a minimum sample size (default 5 disagreements on the same pattern) before suggesting an adjustment. A single outlier rejection doesn't trigger a reweight. The system also tracks calibration history so adjustments can be rolled back if they make scoring worse.

**Q: Why the name ApplyKit?**

It's a toolkit for applying. The name emphasizes that this isn't just evaluation or tracking — it produces ready-to-use application materials. "Kit" implies everything you need is assembled for you. Short, memorable, and it works as both a product name and a CLI command.

---

## MVP FEATURE LIST

| # | Step | Feature | Mode |
|---|------|---------|------|
| 1 | **Scout** | Monitor company career pages, detect new postings | Scheduled |
| 1b | **Scout** | Accept ad-hoc JDs via URL, file, or paste | Ad-hoc |
| 2 | **Score** | Evaluate JDs across 10 configurable weighted dimensions | Both |
| 3 | **Rank** | Sort by weighted score, assign grades, accumulate over time | Both |
| 4 | **Craft** | Generate tailored resume + cover letter for qualifying roles | Both |
| 5 | **Apply** | Review ranked results, approve materials, track status | User-driven |
| 6 | **Track** | Pipeline view across all applications with status state machine | Always-on |
| 7 | **Volume caps** | Score cap (25/run), craft threshold (B+), craft cap (5/run) | Configurable |
| 8 | **Feedback** | Agree/disagree/skip on scored roles with reason logging | User-driven |
| 9 | **Calibrate** | Suggest weight adjustments based on disagreement patterns | On-demand |

## FUTURE FEATURES (design for, don't build)

| # | Feature | How it plugs in |
|---|---------|----------------|
| F1 | **Interview prep** | Trigger on status = INTERVIEWING → generate prep from JD + profile |
| F2 | **Outcome analytics** | Correlate dimension scores with interview/offer outcomes → suggest reweights |
| F3 | **Multi-profile support** | Config swap for different career directions |
| F4 | **Job board integrations** | New Scout sources (Indeed, LinkedIn) — same Score/Rank/Craft pipeline |

## APPENDIX: V1 LESSONS LEARNED

| What happened | Root cause | V2 fix |
|---------------|-----------|--------|
| All 19 files lost after session ended | Written to temp outputs dir, never copied to workspace | Write directly to workspace + push to GitHub |
| Never tested against a real JD | Sandbox was down during build session | Test is a blocking step before "done" |
| No tests at all | Treated as "we'll test later" | pytest suite is part of the build |
| Personal data would have been committed | No .gitignore, no data separation | .gitignore + .example templates from day one |
| Scope mismatch between builder and user | PR/FAQ described a scoring tool, not a pipeline | This rewrite — scheduled overnight pipeline with end-to-end automation |
