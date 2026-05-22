# Claude Code Project Instructions

## Project Overview
This is a short-form creator taxonomy pipeline that automatically generates hierarchical content niches from YouTube video data.

## Important Rules

### Protected Files
**DO NOT DELETE these files:**
- `LEARNINGS.md` - Contains all project learnings, V0/V1 results, and V2/V3/V4 roadmap. This is critical documentation.

### File Structure
- `pipeline/` - Python scripts for data processing
- `pipeline/v0/` - V0 pipeline (proof of concept)
- `pipeline/v1/` - V1 pipeline (4-level hierarchy, multi-label)
- `pipeline/v2/` - V2 pipeline (hashtag co-occurrence - planned)
- `data/` - Generated data files (embeddings, taxonomy, etc.)
- `pages/` - Next.js frontend

### Environment
- Python 3.10+ required
- API keys in `.env.local`: `YOUTUBE_API_KEY`, `OPENAI_API_KEY`
- Run `npm run dev` for the UI
- Run `bash pipeline/v1/run.sh` for the V1 pipeline

### Current Status
- V0: Complete (109 niches)
- V1: Complete (209 niches, 4-level hierarchy)
- V2: Planned (hashtag co-occurrence graph)
- V3: Planned (LLM sub-niche discovery)
- V4: Planned (scale to 20-30K videos)
