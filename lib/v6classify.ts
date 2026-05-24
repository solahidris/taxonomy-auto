import OpenAI from 'openai'
import fs from 'fs'
import path from 'path'

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY })

export const UNKNOWN_THRESHOLD = 0.35
export const HIGH_CONFIDENCE_THRESHOLD = 0.55
export const MULTI_LABEL_GAP = 0.08
export const TOP_N = 5

export type Niche = {
  name: string
  description: string
  keywords: string[]
  category_name: string
  subcategory_name: string
  video_count: number
  top_hashtags: string[]
  centroid: number[]
  exemplar_creators: Array<{ author_id: string; author: string; video_count: number }>
}

export type V6Taxonomy = {
  niches: Record<string, Niche>
  stats: { total_niches: number; total_categories: number; total_videos: number }
}

let taxonomyCache: V6Taxonomy | null = null
let nicheIds: string[] | null = null
let centroidMatrix: number[][] | null = null

export function loadTaxonomy(): V6Taxonomy | null {
  if (taxonomyCache) return taxonomyCache
  const fp = path.join(process.cwd(), 'data', 'v6', 'taxonomy.json')
  if (!fs.existsSync(fp)) return null
  taxonomyCache = JSON.parse(fs.readFileSync(fp, 'utf-8'))

  if (taxonomyCache) {
    nicheIds = []
    const centroids: number[][] = []
    for (const [id, niche] of Object.entries(taxonomyCache.niches)) {
      if (niche.centroid?.length) {
        nicheIds.push(id)
        centroids.push(niche.centroid)
      }
    }
    centroidMatrix = centroids
  }

  return taxonomyCache
}

export function cosine(a: number[], b: number[]): number {
  let dot = 0, na = 0, nb = 0
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i]
  }
  const denom = Math.sqrt(na) * Math.sqrt(nb)
  return denom === 0 ? 0 : dot / denom
}

export function extractHashtags(text: string): string[] {
  const matches = text.match(/#([a-zA-Z][a-zA-Z0-9_]*)/g) || []
  return matches.map(m => m.slice(1).toLowerCase())
}

export function hashtagBoost(inputTags: string[], nicheTags: string[]): number {
  if (!inputTags.length || !nicheTags.length) return 0
  const nicheSet = new Set(nicheTags.map(t => t.toLowerCase()))
  let matched = 0
  for (const tag of inputTags) { if (nicheSet.has(tag)) matched++ }
  return matched > 0 ? 0.12 * Math.min(matched, 3) / 3 : 0
}

export async function classifyText(text: string) {
  const taxonomy = loadTaxonomy()
  if (!taxonomy || !centroidMatrix || !nicheIds) return null

  const inputHashtags = extractHashtags(text)

  const embResp = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: text.slice(0, 1000),
  })
  const vec = embResp.data[0].embedding

  const scores = nicheIds.map((nicheId, i) => {
    const niche = taxonomy.niches[nicheId]
    const embSim = cosine(vec, centroidMatrix![i])
    const boost = hashtagBoost(inputHashtags, niche.top_hashtags || [])
    return { nicheId, score: Math.min(1, embSim + boost), embeddingSim: embSim, hashtagBoost: boost }
  })

  scores.sort((a, b) => b.score - a.score)
  const topScores = scores.slice(0, TOP_N)

  const matches = topScores.map((item, rank) => {
    const niche = taxonomy.niches[item.nicheId]
    const confidence = Math.max(0, Math.min(100, (item.score - 0.2) / 0.5 * 100))
    const matchedHashtags = inputHashtags.filter(tag =>
      (niche.top_hashtags || []).map(t => t.toLowerCase()).includes(tag)
    )
    return {
      rank: rank + 1,
      niche_id: item.nicheId,
      niche_name: niche.name,
      category: niche.category_name,
      subcategory: niche.subcategory_name,
      hierarchy: `${niche.category_name} > ${niche.subcategory_name} > ${niche.name}`,
      confidence: Math.round(confidence * 10) / 10,
      raw_similarity: Math.round(item.score * 10000) / 10000,
      embedding_similarity: Math.round(item.embeddingSim * 10000) / 10000,
      hashtag_boost: Math.round(item.hashtagBoost * 10000) / 10000,
      matched_hashtags: matchedHashtags,
      video_count: niche.video_count,
      top_hashtags: (niche.top_hashtags || []).slice(0, 5),
      exemplar_creators: (niche.exemplar_creators || []).slice(0, 5),
    }
  })

  const bestScore = matches[0]?.raw_similarity || 0
  const primaryMatch = matches[0] || null
  const secondaryMatches = matches.slice(1).filter(m => bestScore - m.raw_similarity < MULTI_LABEL_GAP)

  let classificationStatus: 'UNKNOWN' | 'HIGH_CONFIDENCE' | 'MODERATE'
  let statusMessage: string

  if (bestScore < UNKNOWN_THRESHOLD) {
    classificationStatus = 'UNKNOWN'
    statusMessage = 'No strong match found — this creator may represent an emerging or rare niche.'
  } else if (bestScore >= HIGH_CONFIDENCE_THRESHOLD) {
    classificationStatus = 'HIGH_CONFIDENCE'
    statusMessage = 'Strong match found in taxonomy.'
  } else {
    classificationStatus = 'MODERATE'
    statusMessage = 'Reasonable match found — creator may span multiple niches.'
  }

  return {
    input_text: text,
    input_hashtags: inputHashtags,
    classification_status: classificationStatus,
    status_message: statusMessage,
    is_unknown: bestScore < UNKNOWN_THRESHOLD,
    is_multi_label: secondaryMatches.length > 0,
    primary_niche: primaryMatch,
    secondary_niches: secondaryMatches,
    all_matches: matches,
    stats: {
      best_similarity: bestScore,
      taxonomy_size: taxonomy.stats.total_niches,
      total_videos_indexed: taxonomy.stats.total_videos,
      num_close_matches: 1 + secondaryMatches.length,
    },
  }
}
