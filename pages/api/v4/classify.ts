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
const SUB_NICHE_KEYWORD_BOOST = 0.10

type NicheData = {
  name: string
  description?: string
  category_name: string
  subcategory_name?: string
  video_count: number
  source: 'embedding_clustered' | 'hashtag_discovered'
  hashtag_validated: boolean
  confidence: string
  top_hashtags: string[]
  keywords?: string[]
  centroid?: number[]
  has_sub_niches: boolean
  sub_niche_ids: string[]
}

type SubNiche = {
  id: string
  name: string
  description: string
  source: 'llm_generated'
  validation_status: 'validated' | 'partial'
  video_support: number
  parent_niche_id: string
  parent_niche_name: string
  category_name: string
  subcategory_name: string
  target_audience?: string
  validation_keywords: string[]
  expected_hashtags: string[]
}

type V4Taxonomy = {
  version: string
  categories: Record<string, { name: string }>
  subcategories: Record<string, { name: string }>
  niches: Record<string, NicheData>
  sub_niches: Record<string, SubNiche>
  stats: {
    total_niches: number
    v1_embedding_niches: number
    v2_hashtag_niches: number
    v4_llm_sub_niches: number
  }
}

let taxonomyCache: V4Taxonomy | null = null
let embeddingNicheIds: string[] | null = null
let hashtagNicheIds: string[] | null = null
let centroidMatrix: number[][] | null = null

function loadTaxonomy(): V4Taxonomy | null {
  if (taxonomyCache) return taxonomyCache
  const fp = path.join(process.cwd(), 'data', 'v4', 'taxonomy.json')
  if (!fs.existsSync(fp)) return null
  taxonomyCache = JSON.parse(fs.readFileSync(fp, 'utf-8'))

  if (taxonomyCache) {
    embeddingNicheIds = []
    hashtagNicheIds = []
    const centroids: number[][] = []

    for (const [id, niche] of Object.entries(taxonomyCache.niches)) {
      if (niche.source === 'embedding_clustered' && niche.centroid) {
        embeddingNicheIds.push(id)
        centroids.push(niche.centroid)
      } else if (niche.source === 'hashtag_discovered') {
        hashtagNicheIds.push(id)
      }
    }

    centroidMatrix = centroids
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

function matchSubNiche(text: string, inputHashtags: string[], sub: SubNiche): { score: number; matchedTerms: string[] } {
  const textLower = text.toLowerCase()
  const matchedTerms: string[] = []
  let score = 0

  // Check validation keywords
  for (const keyword of sub.validation_keywords || []) {
    if (textLower.includes(keyword.toLowerCase())) {
      matchedTerms.push(keyword)
      score += 0.15
    }
  }

  // Check expected hashtags
  for (const hashtag of sub.expected_hashtags || []) {
    if (inputHashtags.includes(hashtag.toLowerCase())) {
      matchedTerms.push(`#${hashtag}`)
      score += 0.1
    }
  }

  // Check name keywords
  const nameWords = sub.name.toLowerCase().split(/\s+/)
  for (const word of nameWords) {
    if (word.length > 3 && textLower.includes(word)) {
      matchedTerms.push(word)
      score += 0.05
    }
  }

  // Cap at 1.0
  return { score: Math.min(1, score), matchedTerms: [...new Set(matchedTerms)] }
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end()

  const { text } = req.body as { text?: string }
  if (!text?.trim()) return res.status(400).json({ error: 'text required' })

  const taxonomy = loadTaxonomy()
  if (!taxonomy || !centroidMatrix || !embeddingNicheIds || !hashtagNicheIds) {
    return res.status(503).json({
      error: 'V4 Taxonomy not ready. Run the V4 pipeline first.',
    })
  }

  const inputHashtags = extractHashtags(text)

  // Embed input text
  const embResp = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: text.slice(0, 1000),
  })
  const vec = embResp.data[0].embedding

  // Compute similarities to embedding-based niches
  const embeddingSimilarities = centroidMatrix.map(centroid => cosine(vec, centroid))

  type NicheScore = {
    nicheId: string
    score: number
    embeddingSim: number | null
    hashtagScore: number | null
    matchedHashtags: string[]
    source: 'embedding_clustered' | 'hashtag_discovered'
    subNicheMatches: Array<{
      id: string
      name: string
      score: number
      matchedTerms: string[]
      validation_status: string
    }>
  }

  const allScores: NicheScore[] = []

  // Score embedding-based niches
  for (let i = 0; i < embeddingNicheIds.length; i++) {
    const nicheId = embeddingNicheIds[i]
    const niche = taxonomy.niches[nicheId]
    const embSim = embeddingSimilarities[i]

    const matchedHashtags: string[] = []
    const nicheHashtags = niche.top_hashtags || []
    for (const tag of inputHashtags) {
      if (nicheHashtags.map(h => h.toLowerCase()).includes(tag)) {
        matchedHashtags.push(tag)
      }
    }

    // Check sub-niches
    const subNicheMatches: NicheScore['subNicheMatches'] = []
    for (const subId of niche.sub_niche_ids || []) {
      const sub = taxonomy.sub_niches[subId]
      if (sub) {
        const { score, matchedTerms } = matchSubNiche(text, inputHashtags, sub)
        if (score > 0.1) {
          subNicheMatches.push({
            id: subId,
            name: sub.name,
            score,
            matchedTerms,
            validation_status: sub.validation_status,
          })
        }
      }
    }

    // Sort sub-niches by score
    subNicheMatches.sort((a, b) => b.score - a.score)

    // Calculate final score with boosts
    const hashtagBoost = matchedHashtags.length > 0 ? HASHTAG_MATCH_BOOST * Math.min(matchedHashtags.length, 3) / 3 : 0
    const subNicheBoost = subNicheMatches.length > 0 ? SUB_NICHE_KEYWORD_BOOST * Math.min(subNicheMatches[0].score, 1) : 0
    const finalScore = Math.min(1, embSim + hashtagBoost + subNicheBoost)

    allScores.push({
      nicheId,
      score: finalScore,
      embeddingSim: embSim,
      hashtagScore: hashtagBoost,
      matchedHashtags,
      source: 'embedding_clustered',
      subNicheMatches: subNicheMatches.slice(0, 3),
    })
  }

  // Score hashtag-discovered niches
  for (const nicheId of hashtagNicheIds) {
    const niche = taxonomy.niches[nicheId]
    const nicheHashtags = niche.top_hashtags || []

    const matchedHashtags: string[] = []
    for (const tag of inputHashtags) {
      if (nicheHashtags.map(h => h.toLowerCase()).includes(tag)) {
        matchedHashtags.push(tag)
      }
    }

    const keywords = niche.keywords || []
    const textLower = text.toLowerCase()
    let keywordMatches = 0
    for (const kw of keywords) {
      if (textLower.includes(kw.toLowerCase())) keywordMatches++
    }

    const hashtagScore = computeHashtagScore(inputHashtags, nicheHashtags)
    const keywordBonus = keywords.length > 0 ? (keywordMatches / keywords.length) * 0.2 : 0
    const finalScore = (hashtagScore * 0.6 + keywordBonus) * 0.8

    if (finalScore > 0.1) {
      allScores.push({
        nicheId,
        score: finalScore,
        embeddingSim: null,
        hashtagScore: hashtagScore,
        matchedHashtags,
        source: 'hashtag_discovered',
        subNicheMatches: [],
      })
    }
  }

  // Sort by score
  allScores.sort((a, b) => b.score - a.score)

  // Build top N matches
  const matches = allScores.slice(0, TOP_N).map((item, rank) => {
    const niche = taxonomy.niches[item.nicheId]
    const confidence = computeConfidence(item.score)

    return {
      rank: rank + 1,
      niche_id: item.nicheId,
      niche_name: niche.name,
      category: niche.category_name,
      subcategory: niche.subcategory_name || 'General',
      hierarchy: `${niche.category_name} > ${niche.subcategory_name || 'General'} > ${niche.name}`,
      confidence: Math.round(confidence * 10) / 10,
      raw_similarity: Math.round(item.score * 10000) / 10000,
      source: item.source,
      matched_hashtags: item.matchedHashtags,
      has_sub_niches: niche.has_sub_niches,
      sub_niche_matches: item.subNicheMatches,
      recommended_sub_niche: item.subNicheMatches[0] || null,
      video_count: niche.video_count,
      top_hashtags: niche.top_hashtags?.slice(0, 5) || [],
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
    statusMessage = 'This creator may represent a NEW or UNDERSERVED niche not well covered by current taxonomy.'
  } else if (isHighConfidence) {
    classificationStatus = 'HIGH_CONFIDENCE'
    statusMessage = 'Strong match found in taxonomy.'
  } else {
    classificationStatus = 'MODERATE'
    statusMessage = 'Reasonable match, but creator may span multiple niches or content styles.'
  }

  // Count sources and sub-niche matches
  const embeddingMatches = matches.filter(m => m.source === 'embedding_clustered').length
  const hashtagMatches = matches.filter(m => m.source === 'hashtag_discovered').length
  const subNicheRecommendations = matches.filter(m => m.recommended_sub_niche).length

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
      taxonomy_size: taxonomy.stats.total_niches,
      embedding_niches: taxonomy.stats.v1_embedding_niches,
      hashtag_niches: taxonomy.stats.v2_hashtag_niches,
      llm_sub_niches: taxonomy.stats.v4_llm_sub_niches,
      matches_from_embedding: embeddingMatches,
      matches_from_hashtag: hashtagMatches,
      matches_with_sub_niches: subNicheRecommendations,
    }
  }

  res.status(200).json(response)
}
