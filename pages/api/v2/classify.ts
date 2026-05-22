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
const HASHTAG_MATCH_BOOST = 0.15 // Boost for hashtag matches

type NicheData = {
  name: string
  description?: string
  category_id?: number
  category_name: string
  subcategory_key?: string
  subcategory_name?: string
  video_count: number
  hierarchy_depth?: number
  exemplar_creators?: Array<{
    channel_id: string
    channel_title: string
    video_count: number
  }>
  sample_titles?: string[]
  sample_tags?: string[]
  centroid?: number[]
  source: 'embedding_clustered' | 'hashtag_discovered'
  hashtag_validated: boolean
  confidence: string
  top_hashtags: string[]
  keywords?: string[]
  discovery_reason?: string
}

type V2Taxonomy = {
  version: string
  approach: string
  categories: Record<string, { name: string; description?: string; niche_count?: number }>
  subcategories: Record<string, { name: string; category_id: number; category_name: string; niche_count: number }>
  niches: Record<string, NicheData>
  stats: {
    total_niches: number
    v1_embedding_niches: number
    v2_hashtag_niches: number
    hashtag_validated: number
    high_confidence: number
    total_categories: number
    total_subcategories: number
  }
}

let taxonomyCache: V2Taxonomy | null = null
let embeddingNicheIds: string[] | null = null
let hashtagNicheIds: string[] | null = null
let centroidMatrix: number[][] | null = null

function loadTaxonomy(): V2Taxonomy | null {
  if (taxonomyCache) return taxonomyCache
  const fp = path.join(process.cwd(), 'data', 'v2', 'taxonomy.json')
  if (!fs.existsSync(fp)) return null
  taxonomyCache = JSON.parse(fs.readFileSync(fp, 'utf-8'))

  if (taxonomyCache) {
    // Separate embedding-based and hashtag-based niches
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
  // Map similarity range [0.2, 0.7] to confidence [0, 100]
  return Math.max(0, Math.min(100, (similarity - 0.2) / 0.5 * 100))
}

function extractHashtags(text: string): string[] {
  // Extract hashtags from text (with or without #)
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

  // Score based on proportion of niche hashtags matched, with diminishing returns
  const matchRatio = matchCount / Math.min(nicheHashtags.length, 5)
  return Math.min(1, matchRatio * 1.2) // Cap at 1.0
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end()

  const { text } = req.body as { text?: string }
  if (!text?.trim()) return res.status(400).json({ error: 'text required' })

  const taxonomy = loadTaxonomy()
  if (!taxonomy || !centroidMatrix || !embeddingNicheIds || !hashtagNicheIds) {
    return res.status(503).json({
      error: 'V2 Taxonomy not ready. Run the V2 pipeline first.',
    })
  }

  // Extract hashtags from input
  const inputHashtags = extractHashtags(text)

  // Embed input text
  const embResp = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: text.slice(0, 1000),
  })
  const vec = embResp.data[0].embedding

  // Compute similarities to embedding-based niches
  const embeddingSimilarities = centroidMatrix.map(centroid => cosine(vec, centroid))

  // Build scores for all niches
  type NicheScore = {
    nicheId: string
    score: number
    embeddingSim: number | null
    hashtagScore: number | null
    matchedHashtags: string[]
    source: 'embedding_clustered' | 'hashtag_discovered'
  }

  const allScores: NicheScore[] = []

  // Score embedding-based niches
  for (let i = 0; i < embeddingNicheIds.length; i++) {
    const nicheId = embeddingNicheIds[i]
    const niche = taxonomy.niches[nicheId]
    const embSim = embeddingSimilarities[i]

    // Check if input hashtags match this niche's hashtags
    const matchedHashtags: string[] = []
    const nicheHashtags = niche.top_hashtags || []
    for (const tag of inputHashtags) {
      if (nicheHashtags.map(h => h.toLowerCase()).includes(tag)) {
        matchedHashtags.push(tag)
      }
    }

    // Boost embedding similarity if hashtags match
    const hashtagBoost = matchedHashtags.length > 0 ? HASHTAG_MATCH_BOOST * Math.min(matchedHashtags.length, 3) / 3 : 0
    const finalScore = Math.min(1, embSim + hashtagBoost)

    allScores.push({
      nicheId,
      score: finalScore,
      embeddingSim: embSim,
      hashtagScore: hashtagBoost,
      matchedHashtags,
      source: 'embedding_clustered',
    })
  }

  // Score hashtag-discovered niches (no embedding, only hashtag matching)
  for (const nicheId of hashtagNicheIds) {
    const niche = taxonomy.niches[nicheId]
    const nicheHashtags = niche.top_hashtags || []

    const matchedHashtags: string[] = []
    for (const tag of inputHashtags) {
      if (nicheHashtags.map(h => h.toLowerCase()).includes(tag)) {
        matchedHashtags.push(tag)
      }
    }

    // For hashtag-only niches, also use keyword matching on the text
    const keywords = niche.keywords || []
    const textLower = text.toLowerCase()
    let keywordMatches = 0
    for (const kw of keywords) {
      if (textLower.includes(kw.toLowerCase())) keywordMatches++
    }

    // Compute hashtag score
    const hashtagScore = computeHashtagScore(inputHashtags, nicheHashtags)

    // Keyword bonus (smaller weight)
    const keywordBonus = keywords.length > 0 ? (keywordMatches / keywords.length) * 0.2 : 0

    // Final score: combination of hashtag matching and keyword matching
    // Scale to be comparable to embedding similarity range
    const finalScore = (hashtagScore * 0.6 + keywordBonus) * 0.8 // Max ~0.64 for pure hashtag match

    if (finalScore > 0.1) { // Only include if there's meaningful signal
      allScores.push({
        nicheId,
        score: finalScore,
        embeddingSim: null,
        hashtagScore: hashtagScore,
        matchedHashtags,
        source: 'hashtag_discovered',
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
      exemplar_creators: niche.exemplar_creators?.slice(0, 5) || [],
      sample_titles: niche.sample_titles?.slice(0, 5) || [],
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

  // Count sources in results
  const embeddingMatches = matches.filter(m => m.source === 'embedding_clustered').length
  const hashtagMatches = matches.filter(m => m.source === 'hashtag_discovered').length

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
      matches_from_embedding: embeddingMatches,
      matches_from_hashtag: hashtagMatches,
    }
  }

  res.status(200).json(response)
}
