import type { NextApiRequest, NextApiResponse } from 'next'
import OpenAI from 'openai'
import fs from 'fs'
import path from 'path'

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY })

// Classification thresholds
const UNKNOWN_THRESHOLD = 0.35
const HIGH_CONFIDENCE_THRESHOLD = 0.55
const MULTI_LABEL_GAP = 0.08
const TOP_N = 5
const HASHTAG_MATCH_BOOST = 0.15
const KEYWORD_MATCH_BOOST = 0.10

type V5Niche = {
  id: string
  name: string
  description: string
  keywords: string[]
  source: string
  platforms: string[]
  video_count: number
  top_hashtags: string[]
}

type V5Category = {
  id: string
  name: string
  description: string
  source: string
  children: V5Niche[]
}

type V5Taxonomy = {
  version: string
  generated_at: string
  platforms: string[]
  approach: string
  stats: {
    v4_niches: number
    v5_new_niches: number
    cross_platform_validated: number
  }
  categories: V5Category[]
  total_niches: number
  platform_distribution: Record<string, number>
}

let taxonomyCache: V5Taxonomy | null = null
let allNiches: V5Niche[] = []
const nicheEmbeddings: Map<string, number[]> = new Map()

function loadTaxonomy(): V5Taxonomy | null {
  if (taxonomyCache) return taxonomyCache
  const fp = path.join(process.cwd(), 'data', 'v5', 'taxonomy.json')
  if (!fs.existsSync(fp)) return null
  taxonomyCache = JSON.parse(fs.readFileSync(fp, 'utf-8'))

  if (taxonomyCache) {
    // Flatten niches from categories
    allNiches = []
    for (const category of taxonomyCache.categories) {
      for (const niche of category.children) {
        allNiches.push(niche)
      }
    }
  }

  return taxonomyCache
}

function cosine(a: number[], b: number[]): number {
  let dot = 0, na = 0, nb = 0
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i]
    na += a[i] * a[i]
    nb += b[i] * b[i]
  }
  const denom = Math.sqrt(na) * Math.sqrt(nb)
  return denom === 0 ? 0 : dot / denom
}

function computeConfidence(similarity: number): number {
  return Math.max(0, Math.min(100, (similarity - 0.2) / 0.5 * 100))
}

function extractHashtags(text: string): string[] {
  const hashtagPattern = /#?([a-zA-Z][a-zA-Z0-9_]*)/g
  const matches = text.toLowerCase().match(hashtagPattern) || []
  return matches.map(m => m.replace('#', '').toLowerCase())
}

function computeHashtagScore(inputHashtags: string[], nicheHashtags: string[]): number {
  if (inputHashtags.length === 0 || nicheHashtags.length === 0) return 0
  const nicheSet = new Set(nicheHashtags.map(h => h.toLowerCase()))
  let matchCount = 0
  for (const tag of inputHashtags) {
    if (nicheSet.has(tag)) matchCount++
  }
  const matchRatio = matchCount / Math.min(nicheHashtags.length, 5)
  return Math.min(1, matchRatio * 1.2)
}

function computeKeywordScore(text: string, keywords: string[]): { score: number; matchedKeywords: string[] } {
  if (keywords.length === 0) return { score: 0, matchedKeywords: [] }
  const textLower = text.toLowerCase()
  const matchedKeywords: string[] = []

  for (const keyword of keywords) {
    const kw = keyword.replace(/^#/, '').toLowerCase()
    if (textLower.includes(kw)) {
      matchedKeywords.push(keyword)
    }
  }

  const score = matchedKeywords.length > 0
    ? Math.min(1, (matchedKeywords.length / Math.min(keywords.length, 5)) * 1.2)
    : 0

  return { score, matchedKeywords }
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end()

  const { text } = req.body as { text?: string }
  if (!text?.trim()) return res.status(400).json({ error: 'text required' })

  const taxonomy = loadTaxonomy()
  if (!taxonomy || allNiches.length === 0) {
    return res.status(503).json({
      error: 'V5 Taxonomy not ready. Run the V5 pipeline first.',
    })
  }

  const inputHashtags = extractHashtags(text)

  // Embed input text
  const embResp = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: text.slice(0, 1000),
  })
  const vec = embResp.data[0].embedding

  // Embed niche descriptions for semantic matching (cached)
  const nicheDescriptions = allNiches.map(n => `${n.name}: ${n.description}`)

  // Generate embeddings for niches if not cached
  if (nicheEmbeddings.size === 0) {
    const batchSize = 50
    for (let i = 0; i < nicheDescriptions.length; i += batchSize) {
      const batch = nicheDescriptions.slice(i, i + batchSize)
      const batchResp = await openai.embeddings.create({
        model: 'text-embedding-3-small',
        input: batch,
      })
      for (let j = 0; j < batchResp.data.length; j++) {
        nicheEmbeddings.set(allNiches[i + j].id, batchResp.data[j].embedding)
      }
    }
  }

  type NicheScore = {
    nicheId: string
    score: number
    embeddingSim: number
    hashtagScore: number
    keywordScore: number
    matchedHashtags: string[]
    matchedKeywords: string[]
    platforms: string[]
  }

  const allScores: NicheScore[] = []

  // Score each niche
  for (const niche of allNiches) {
    const nicheEmb = nicheEmbeddings.get(niche.id)
    const embSim = nicheEmb ? cosine(vec, nicheEmb) : 0

    // Hashtag matching
    const nicheHashtags = niche.top_hashtags || []
    const matchedHashtags: string[] = []
    for (const tag of inputHashtags) {
      if (nicheHashtags.map(h => h.toLowerCase()).includes(tag)) {
        matchedHashtags.push(tag)
      }
    }

    // Keyword matching
    const { score: keywordScore, matchedKeywords } = computeKeywordScore(text, niche.keywords || [])

    // Calculate final score with boosts
    const hashtagBoost = matchedHashtags.length > 0
      ? HASHTAG_MATCH_BOOST * Math.min(matchedHashtags.length, 3) / 3
      : 0
    const keywordBoost = keywordScore > 0 ? KEYWORD_MATCH_BOOST * keywordScore : 0
    const finalScore = Math.min(1, embSim + hashtagBoost + keywordBoost)

    allScores.push({
      nicheId: niche.id,
      score: finalScore,
      embeddingSim: embSim,
      hashtagScore: hashtagBoost,
      keywordScore: keywordBoost,
      matchedHashtags,
      matchedKeywords,
      platforms: niche.platforms,
    })
  }

  // Sort by score
  allScores.sort((a, b) => b.score - a.score)

  // Build top N matches
  const nicheMap = new Map(allNiches.map(n => [n.id, n]))
  const matches = allScores.slice(0, TOP_N).map((item, rank) => {
    const niche = nicheMap.get(item.nicheId)!
    const confidence = computeConfidence(item.score)

    return {
      rank: rank + 1,
      niche_id: item.nicheId,
      niche_name: niche.name,
      description: niche.description,
      platforms: item.platforms,
      confidence: Math.round(confidence * 10) / 10,
      raw_similarity: Math.round(item.score * 10000) / 10000,
      matched_hashtags: item.matchedHashtags,
      matched_keywords: item.matchedKeywords,
      video_count: niche.video_count,
      top_hashtags: niche.top_hashtags?.slice(0, 5) || [],
      is_multi_platform: item.platforms.length >= 2,
    }
  })

  // Determine primary/secondary labels
  const bestScore = matches[0]?.raw_similarity || 0
  const primaryMatches = matches.length > 0 ? [matches[0]] : []
  const secondaryMatches = matches.slice(1).filter(m => bestScore - m.raw_similarity < MULTI_LABEL_GAP)

  // Open-set detection
  const isUnknown = bestScore < UNKNOWN_THRESHOLD
  const isHighConfidence = bestScore >= HIGH_CONFIDENCE_THRESHOLD

  let classificationStatus: 'UNKNOWN' | 'HIGH_CONFIDENCE' | 'MODERATE'
  let statusMessage: string

  if (isUnknown) {
    classificationStatus = 'UNKNOWN'
    statusMessage = 'This creator may represent a NEW niche not yet in the cross-platform taxonomy.'
  } else if (isHighConfidence) {
    classificationStatus = 'HIGH_CONFIDENCE'
    statusMessage = 'Strong match found in cross-platform taxonomy.'
  } else {
    classificationStatus = 'MODERATE'
    statusMessage = 'Reasonable match, but creator may span multiple niches or platforms.'
  }

  // Platform stats
  const platformBreakdown = {
    tiktok: matches.filter(m => m.platforms.includes('tiktok')).length,
    instagram: matches.filter(m => m.platforms.includes('instagram')).length,
    youtube: matches.filter(m => m.platforms.includes('youtube')).length,
  }
  const multiPlatformMatches = matches.filter(m => m.is_multi_platform).length

  const response = {
    input_bio: text,
    input_hashtags: inputHashtags,
    classification_status: classificationStatus,
    status_message: statusMessage,
    is_unknown_niche: isUnknown,
    is_multi_label: secondaryMatches.length > 0,
    primary_niche: primaryMatches[0] || null,
    secondary_niches: secondaryMatches,
    all_matches: matches,
    recommended_labels: [...primaryMatches, ...secondaryMatches],
    stats: {
      best_similarity: bestScore,
      similarity_gap_to_2nd: matches.length > 1 ? bestScore - matches[1].raw_similarity : 0,
      num_close_matches: primaryMatches.length + secondaryMatches.length,
      taxonomy_size: taxonomy.total_niches,
      platforms_in_taxonomy: taxonomy.platforms,
      platform_breakdown: platformBreakdown,
      multi_platform_matches: multiPlatformMatches,
    }
  }

  res.status(200).json(response)
}
