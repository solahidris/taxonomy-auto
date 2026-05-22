import type { NextApiRequest, NextApiResponse } from 'next'
import fs from 'fs'
import path from 'path'

type V2Taxonomy = {
  version: string
  approach: string
  categories: Record<string, { name: string; description?: string; niche_count?: number }>
  subcategories: Record<string, { name: string; category_id: number; category_name: string; niche_count: number }>
  niches: Record<string, {
    name: string
    description?: string
    source: 'embedding_clustered' | 'hashtag_discovered'
    confidence: string
    hashtag_validated: boolean
    top_hashtags: string[]
    video_count: number
    category_name: string
    subcategory_name?: string
    keywords?: string[]
    discovery_reason?: string
    cohesion_score?: number
    exemplar_creators?: Array<{ channel_id: string; channel_title: string; video_count: number }>
    sample_titles?: string[]
  }>
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

type V2Evaluation = {
  v1_metrics: { total_niches: number; total_categories: number; gini_coefficient: number }
  v2_metrics: { total_niches: number; total_categories: number; gini_coefficient: number }
  v2_specific: {
    source_distribution: Record<string, number>
    confidence_distribution: Record<string, number>
    hashtag_validated: number
    hashtag_validated_pct: number
    new_niches_added: number
  }
  comparison: {
    v1_niches: number
    v2_niches: number
    new_in_v2: number
    growth_pct: number
  }
  graph_metrics: {
    total_videos: number
    videos_with_hashtags: number
    hashtag_coverage_pct: number
    unique_hashtags: number
    hashtag_edges: number
  }
  overall_score: number
  score_breakdown: {
    coverage: number
    balance: number
    hashtag_validation: number
    new_discoveries: number
  }
  success_criteria: Record<string, boolean>
}

let taxonomyCache: V2Taxonomy | null = null
let evaluationCache: V2Evaluation | null = null

function loadTaxonomy(): V2Taxonomy | null {
  if (taxonomyCache) return taxonomyCache
  const fp = path.join(process.cwd(), 'data', 'v2', 'taxonomy.json')
  if (!fs.existsSync(fp)) return null
  taxonomyCache = JSON.parse(fs.readFileSync(fp, 'utf-8'))
  return taxonomyCache
}

function loadEvaluation(): V2Evaluation | null {
  if (evaluationCache) return evaluationCache
  const fp = path.join(process.cwd(), 'data', 'v2', 'evaluation.json')
  if (!fs.existsSync(fp)) return null
  evaluationCache = JSON.parse(fs.readFileSync(fp, 'utf-8'))
  return evaluationCache
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') return res.status(405).end()

  const taxonomy = loadTaxonomy()
  const evaluation = loadEvaluation()

  if (!taxonomy) {
    return res.status(503).json({
      error: 'V2 Taxonomy not ready. Run the V2 pipeline first.',
      ready: false,
    })
  }

  // Get new hashtag-discovered niches
  const newNiches = Object.entries(taxonomy.niches)
    .filter(([_, n]) => n.source === 'hashtag_discovered')
    .map(([id, n]) => ({
      id,
      name: n.name,
      description: n.description,
      top_hashtags: n.top_hashtags,
      video_count: n.video_count,
      discovery_reason: n.discovery_reason,
      category_name: n.category_name,
    }))
    .sort((a, b) => b.video_count - a.video_count)

  // Build hierarchical structure for UI
  const hierarchy: Record<string, {
    name: string
    subcategories: Record<string, {
      name: string
      niches: Array<{
        id: string
        name: string
        video_count: number
        source: string
        top_hashtags: string[]
      }>
    }>
  }> = {}

  // Initialize categories
  for (const [catId, catData] of Object.entries(taxonomy.categories)) {
    hierarchy[catId] = {
      name: catData.name,
      subcategories: {}
    }
  }

  // Group niches by category and subcategory
  for (const [nicheId, nicheData] of Object.entries(taxonomy.niches)) {
    const catName = nicheData.category_name
    const subcatName = nicheData.subcategory_name || 'General'

    // Find category by name
    let catId = Object.entries(taxonomy.categories).find(([_, c]) => c.name === catName)?.[0]
    if (!catId) catId = 'cat_hashtag' // fallback for hashtag discovered

    if (!hierarchy[catId]) {
      hierarchy[catId] = { name: catName, subcategories: {} }
    }

    const subcatKey = `${catId}_${subcatName.replace(/\s+/g, '_').toLowerCase()}`
    if (!hierarchy[catId].subcategories[subcatKey]) {
      hierarchy[catId].subcategories[subcatKey] = { name: subcatName, niches: [] }
    }

    hierarchy[catId].subcategories[subcatKey].niches.push({
      id: nicheId,
      name: nicheData.name,
      video_count: nicheData.video_count,
      source: nicheData.source,
      top_hashtags: nicheData.top_hashtags || [],
    })
  }

  // Sort niches by video count within each subcategory
  for (const cat of Object.values(hierarchy)) {
    for (const subcat of Object.values(cat.subcategories)) {
      subcat.niches.sort((a, b) => b.video_count - a.video_count)
    }
  }

  res.status(200).json({
    ready: true,
    stats: taxonomy.stats,
    evaluation: evaluation ? {
      overall_score: evaluation.overall_score,
      score_breakdown: evaluation.score_breakdown,
      comparison: evaluation.comparison,
      graph_metrics: evaluation.graph_metrics,
      success_criteria: evaluation.success_criteria,
    } : null,
    newNiches,
    hierarchy,
    categories: Object.entries(taxonomy.categories).map(([id, data]) => ({
      id,
      ...data
    })),
  })
}
