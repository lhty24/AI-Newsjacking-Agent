# We Built an AI That Reads Crypto News and Writes Tweets About It (So You Don't Have To)

*Introducing the AI Newsjacking Agent — the latest tool from Iliad AI.*

---

Crypto never sleeps. A protocol gets hacked at 3 AM, Bitcoin rips 8% while you're in the shower, and by the time you've drafted a tweet about it, the timeline has already moved on. In this market, the window between "breaking news" and "old news" can be measured in minutes.

That's the problem we set out to solve. Today, we're excited to share what we've been building at Iliad AI: the **AI Newsjacking Agent** — an end-to-end pipeline that ingests real-time crypto news, analyzes it, generates ready-to-post content in multiple styles, and picks the best one. Automatically.

Think of it as your always-on crypto content engine. It watches the news so you can focus on everything else.

---

## What It Actually Does

Here's the short version: the AI Newsjacking Agent pulls the latest crypto news, runs it through a series of AI-powered stages, and produces polished, tweet-ready content — scored and ranked by quality — in seconds.

It doesn't just summarize headlines. It *understands* market sentiment, extracts trading signals, and generates content that matches the voice you need — whether that's a data-driven analyst take, a meme-heavy degen post, or a spicy contrarian thread.

The output? The single best piece of content for each news story, ready to ship.

---

## For the Non-Technical Crowd: What This Means for You

Let's skip the jargon and talk about what this tool actually does in plain language.

### Your Newsroom Assistant That Never Sleeps

Imagine you hired a junior analyst who does nothing but monitor crypto news 24/7. Every time something noteworthy drops — an ETF approval, a protocol exploit, a whale wallet moving billions — this analyst reads the article, figures out the sentiment (bullish? bearish? meh?), identifies the key coins involved, and writes up three different tweet drafts for you:

1. **The Analyst Take** — professional, data-driven, the kind of tweet that makes you look like you know your stuff.
2. **The Meme Take** — emojis, slang, CT energy. The one that goes viral.
3. **The Contrarian Take** — the "actually, here's why everyone is wrong" angle. Thought-provoking, engagement-bait in the best way.

Then this analyst picks the best draft, hands it to you, and moves on to the next story. That's what this tool does.

### Who Is This For?

If you work in crypto and content is part of your job, this is for you:

- **Community managers** drowning in the "post something about this" requests from their team. Instead of scrambling to draft a response every time a token pumps or a protocol gets exploited, you've got three drafts waiting for you before you even open Twitter.
- **Crypto marketers** who need to stay on top of every market-moving event. Newsjacking only works if you're fast. This tool makes you fast.
- **Founders and project leads** who want a consistent social presence but don't have time to write tweets all day. The agent keeps your feed active and relevant, even when you're heads-down building.
- **Content creators** looking for a starting point — a first draft they can riff on. Writer's block doesn't exist when you've got three AI-generated angles to react to.

You don't need to write a single line of code to benefit from the output. The agent produces tweet-ready text that you can copy, tweak, and post. Add your own flair, adjust the tone, or use it as-is. Or, once we ship the distribution layer (more on that below), it'll post for you automatically.

### What the Output Looks Like

Say Bitcoin just crossed $100K on the back of record ETF inflows. The agent would produce something like:

> **Analytical:** "BTC crosses $100K for the first time. Institutional ETF inflows hit $2.4B this week — the supply squeeze thesis is playing out in real time."

> **Meme:** "100K BTC CLUB WE ARE SO BACK 🚀🚀🚀 bears in absolute shambles rn"

> **Contrarian:** "Everyone's celebrating $100K BTC. But who's asking where the exit liquidity comes from when retail FOMO peaks? This is where the smart money starts trimming."

The agent scores all three, picks the strongest one (based on hook strength, clarity, engagement potential, and relevance), and surfaces it as the winner.

---

## Under the Hood: How It Works

For the engineers and the technically curious — here's where it gets fun.

### The Architecture

The system is a five-stage pipeline, each stage handled by its own module:

```
News Ingestion → Analysis → Content Generation → Scoring → Distribution
```

A single `run_pipeline()` function orchestrates the whole thing. This same function is reused across all three execution modes — CLI, REST API, and scheduled jobs. One function, three interfaces. Clean and simple.

### The Tech Stack

We kept the stack lean and deliberate:

- **Python** as the backbone
- **LiteLLM** for unified LLM access (swap between OpenAI, Claude, and others with a config change)
- **Pydantic** for type-safe data models — five models define the contracts between every stage
- **httpx** for async-capable HTTP requests
- **tenacity** for retry logic with exponential backoff on every external call

No database for the MVP. No vector store. No embeddings. Just direct LLM prompting and clean data flow.

### Why No RAG?

This was a deliberate choice. RAG (Retrieval-Augmented Generation) is the go-to pattern for a lot of LLM applications right now, and for good reason — it's powerful when you need to query a large knowledge base or inject domain-specific context. But for newsjacking, the context is *the article itself*. There's no corpus to retrieve from. The news just happened.

We pass the full news content directly into the prompt — no retrieval step, no embedding pipeline, no vector database. This keeps the architecture simple, the latency low, and the iteration speed fast. One less moving part means one less thing to break at 3 AM when the market is melting down. If we later add historical signal tracking (e.g., "last time ETF news broke, meme-style content outperformed analytical by 3x"), that's when RAG earns its place.

### The Interesting Design Decisions

**Temperature as a creative dial.** Each content style uses a different LLM temperature. Analytical tweets get a low temperature (0.3) for focused, consistent output. Contrarian takes get a mid-range temperature (0.7) for balanced creativity. Meme posts crank it up to 0.9 for maximum chaos and variety. Temperature isn't just a parameter here — it's a first-class design decision that shapes the personality of each style.

**LLM-as-judge scoring.** Instead of picking content randomly or using simple heuristics, we send all three variants for a given article to the LLM in a single prompt and ask it to score them on a weighted rubric:

| Criterion | Weight |
|-----------|--------|
| Hook Strength | 30% |
| Clarity | 25% |
| Engagement Potential | 25% |
| Relevance | 20% |

The key insight: scoring all three variants *together* enables relative comparison. The LLM isn't scoring in a vacuum — it's picking the best of three, which produces much more consistent rankings than scoring each one independently.

**Graceful degradation everywhere.** This was a core design principle. If analysis fails for one article, the pipeline skips it and continues with the rest. If one content style fails to generate, the other two still get scored. If scoring itself fails, the pipeline falls back to the first variant instead of crashing. The system always tries to produce *something* useful, even when individual components hiccup.

### How a News Article Flows Through the Pipeline

1. **Ingestion** — The agent fetches the latest articles from CoinGecko's news API. It extracts tickers using a triple-strategy approach (coin ID mapping, ticker symbol regex, and full coin name matching) and deduplicates by normalized title.

2. **Analysis** — Each article gets sent to the LLM with a structured prompt. The response comes back as JSON: sentiment (bullish/bearish/neutral), topic tags, a summary, and a trading signal.

3. **Generation** — For each analyzed article, three content variants are generated — one per style, each with its own temperature setting. The LLM returns tweet text capped at 280 characters.

4. **Scoring** — All three variants for an article are scored together in a single LLM call. The weighted rubric produces a composite score, and the top variant is selected.

5. **Output** — The best variant per article is surfaced. In the current MVP, this means printing to the console. Soon, it'll mean posting to Twitter.

The whole pipeline runs in under 20 seconds for a batch of articles. Every stage logs its execution time and article count for observability.

---

## What's Next

The AI Newsjacking Agent is currently at its Phase 1 MVP — the core pipeline is built, tested, and working. But we've got a lot more planned.

**Phase 2: REST API.** We're wrapping the pipeline in FastAPI endpoints so it can be triggered remotely, integrated into workflows, and monitored via standard HTTP calls. Endpoints for fetching news, triggering runs, posting specific variants, and listing past runs are all specced out.

**Phase 3: Dashboard.** A Streamlit-based frontend for real-time monitoring. See what news the agent is tracking, review generated content before it goes live, and track performance over time.

**Phase 4: Auto-distribution.** The big one. Twitter/X integration via Tweepy, so the agent doesn't just generate content — it posts it. Fully automated, with status tracking and error handling built in.

**Phase 5: Scheduled automation.** APScheduler integration so the pipeline runs on a cadence — every 15 minutes, every hour, whatever fits your strategy. Set it and forget it.

**Phase 6: Learning from the real world.** This is where it gets really interesting. Once we have distribution data (impressions, engagement, retweets), we can feed that back into the scoring model. The LLM-as-judge rubric becomes calibrated against *actual performance*, not just theoretical quality. We're also planning SQLite persistence for run history and prompt tuning based on what actually resonates.

Looking further out, we're exploring multi-platform distribution (Farcaster, Lens, Telegram), multi-language support, and historical signal correlation — using past market reactions to similar news events to inform content strategy.

---

## Why We Built This

Let's zoom out for a second. The crypto content game is broken. There are thousands of tokens, dozens of news sources, and a timeline that moves faster than any human can keep up with. Most crypto teams handle this one of two ways: they either hire a content person who burns out in six months trying to be everywhere at once, or they just let their social presence go quiet when things get busy.

Neither option is great. We think there's a third way: let AI handle the speed, and let humans handle the strategy.

The AI Newsjacking Agent isn't here to replace your content team. It's here to give them superpowers. The AI handles the grunt work — monitoring, analyzing, drafting — so your team can focus on the high-leverage stuff: building relationships, crafting narratives, and making the judgment calls that only humans can make.

## Building in Public

The AI Newsjacking Agent is part of a bigger vision at Iliad AI: building intelligent tools that make crypto professionals faster, sharper, and more consistent. The crypto market moves at a pace that no human content team can match alone. But with the right AI infrastructure, you don't have to.

We're building this in the open because we believe the best tools get built with feedback from the people who use them. If you're a crypto marketer, community manager, or founder who's tired of watching news cycles pass you by — we're building this for you.

Stay tuned. The best is yet to come.

*— The Iliad AI Team*
