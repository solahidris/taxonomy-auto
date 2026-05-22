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

type NicheData = {
  name: string
  category_id: number
  category_name: string
  subcategory_key: string
  subcategory_name: string
  video_count: number
  hierarchy_depth: number
  exemplar_creators: Array<{
    channel_id: string
    channel_title: string
    video_count: number
  }>
  sample_titles: string[]
  sample_tags: string[]
  centroid: number[]
}

type Taxonomy = {
  categories: Record<number, { name: string; niche_count: number }>
  subcategories: Record<string, { name: string; category_id: number; category_name: string; niche_count: number }>
  niches: Record<string, NicheData>
  stats: {
    total_niches: number
    total_categories: number
    total_subcategories: number
    total_videos: number
  }
}

let taxonomyCache: Taxonomy | null = null
let centroidMatrix: number[][] | null = null
let nicheIds: string[] | null = null

function loadTaxonomy(): Taxonomy | null {
  if (taxonomyCache) return taxonomyCache
  const fp = path.join(process.cwd(), 'data', 'v1', 'taxonomy.json')
  if (!fs.existsSync(fp)) return null
  taxonomyCache = JSON.parse(fs.readFileSync(fp, 'utf-8'))

  // Pre-compute centroid matrix
  if (taxonomyCache) {
    nicheIds = Object.keys(taxonomyCache.niches)
    centroidMatrix = nicheIds.map(id => taxonomyCache!.niches[id].centroid)
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

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end()

  const { text } = req.body as { text?: string }
  if (!text?.trim()) return res.status(400).json({ error: 'text required' })

  const taxonomy = loadTaxonomy()
  if (!taxonomy || !centroidMatrix || !nicheIds) {
    return res.status(503).json({
      error: 'V1 Taxonomy not ready. Run the V1 pipeline first.',
    })
  }

  // Embed input text
  const embResp = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: text.slice(0, 1000),
  })
  const vec = embResp.data[0].embedding

  // Compute similarities to all niches
  const similarities = centroidMatrix.map(centroid => cosine(vec, centroid))

  // Sort by similarity
  const sortedIndices = similarities
    .map((sim, idx) => ({ sim, idx }))
    .sort((a, b) => b.sim - a.sim)

  // Build top N matches
  const matches = sortedIndices.slice(0, TOP_N).map((item, rank) => {
    const nicheId = nicheIds![item.idx]
    const niche = taxonomy.niches[nicheId]
    const confidence = computeConfidence(item.sim)

    return {
      rank: rank + 1,
      niche_id: nicheId,
      niche_name: niche.name,
      category: niche.category_name,
      subcategory: niche.subcategory_name,
      hierarchy: `${niche.category_name} > ${niche.subcategory_name} > ${niche.name}`,
      confidence: Math.round(confidence * 10) / 10,
      raw_similarity: Math.round(item.sim * 10000) / 10000,
      exemplar_creators: niche.exemplar_creators.slice(0, 5),
      sample_titles: niche.sample_titles.slice(0, 5),
      video_count: niche.video_count,
    }
  })

  // Determine primary/secondary labels
  const bestSim = matches[0]?.raw_similarity || 0
  const primaryMatches = matches.length > 0 ? [matches[0]] : []
  const secondaryMatches = matches.slice(1).filter(m => bestSim - m.raw_similarity < MULTI_LABEL_GAP)

  // Open-set detection
  const isUnknown = bestSim < UNKNOWN_THRESHOLD
  const isHighConfidence = bestSim >= HIGH_CONFIDENCE_THRESHOLD

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
    statusMessage = 'Reasonable match, but creator may span multiple niches.'
  }

  const response = {
    input_bio: text,
    classification_status: classificationStatus,
    status_message: statusMessage,
    is_unknown_niche: isUnknown,
    is_multi_label: secondaryMatches.length > 0,
    primary_niche: primaryMatches[0] || null,
    secondary_niches: secondaryMatches,
    all_matches: matches,
    recommended_labels: [...primaryMatches, ...secondaryMatches],
    stats: {
      best_similarity: bestSim,
      similarity_gap_to_2nd: matches.length > 1 ? bestSim - matches[1].raw_similarity : 0,
      num_close_matches: primaryMatches.length + secondaryMatches.length,
      taxonomy_size: taxonomy.stats.total_niches,
    }
  }

  res.status(200).json(response)
}
