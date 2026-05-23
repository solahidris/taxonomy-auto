import type { NextApiRequest, NextApiResponse } from 'next'
import fs from 'fs'
import path from 'path'

type Niche = {
  name: string
  description: string
  keywords: string[]
  category_id: number
  category_name: string
  subcategory_id: string
  subcategory_name: string
  video_count: number
  top_hashtags: string[]
  centroid: number[]
  exemplar_creators: Array<{ author_id: string; author: string; video_count: number }>
  source: string
}

type V6Taxonomy = {
  version: string
  generated_at: string
  approach: string
  sources: Record<string, string>
  categories: Record<string, { name: string; description: string; niche_count: number }>
  subcategories: Record<string, { name: string; description: string; category_id: number; category_name: string; niche_count: number }>
  niches: Record<string, Niche>
  stats: {
    total_niches: number
    total_categories: number
    total_subcategories: number
    total_videos: number
    approaches: string[]
  }
}

type V6Evaluation = {
  total_niches: number
  total_categories: number
  coverage: number
  gini_coefficient: number
  niche_sizes: { max: number; min: number; median: number; mean: number }
  scores: { coverage: number; balance: number; scale: number; overall: number }
  category_distribution: Record<string, number>
}

let taxonomyCache: V6Taxonomy | null = null
let evaluationCache: V6Evaluation | null = null

function loadTaxonomy(): V6Taxonomy | null {
  if (taxonomyCache) return taxonomyCache
  const fp = path.join(process.cwd(), 'data', 'v6', 'taxonomy.json')
  if (!fs.existsSync(fp)) return null
  taxonomyCache = JSON.parse(fs.readFileSync(fp, 'utf-8'))
  return taxonomyCache
}

function loadEvaluation(): V6Evaluation | null {
  if (evaluationCache) return evaluationCache
  const fp = path.join(process.cwd(), 'data', 'v6', 'evaluation.json')
  if (!fs.existsSync(fp)) return null
  evaluationCache = JSON.parse(fs.readFileSync(fp, 'utf-8'))
  return evaluationCache
}

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') return res.status(405).end()

  const taxonomy = loadTaxonomy()
  if (!taxonomy) {
    return res.status(503).json({
      error: 'V6 Taxonomy not ready. Run pipeline/v6/run.sh first.',
      ready: false,
    })
  }

  const evaluation = loadEvaluation()

  // Build hierarchical structure for UI
  const hierarchy: Record<string, {
    name: string
    description: string
    subcategories: Record<string, {
      name: string
      niches: Array<{ id: string; name: string; video_count: number; top_hashtags: string[] }>
    }>
  }> = {}

  for (const [catId, catData] of Object.entries(taxonomy.categories)) {
    hierarchy[catId] = { name: catData.name, description: catData.description, subcategories: {} }
  }

  for (const [nicheId, nicheData] of Object.entries(taxonomy.niches)) {
    const catKey = `cat_${nicheData.category_id}`
    const subcatKey = nicheData.subcategory_id

    if (!hierarchy[catKey]) {
      hierarchy[catKey] = { name: nicheData.category_name, description: '', subcategories: {} }
    }
    if (!hierarchy[catKey].subcategories[subcatKey]) {
      const subcat = taxonomy.subcategories[subcatKey]
      hierarchy[catKey].subcategories[subcatKey] = {
        name: subcat?.name || nicheData.subcategory_name,
        niches: [],
      }
    }

    hierarchy[catKey].subcategories[subcatKey].niches.push({
      id: nicheId,
      name: nicheData.name,
      video_count: nicheData.video_count,
      top_hashtags: nicheData.top_hashtags?.slice(0, 5) || [],
    })
  }

  // Sort niches by video count
  for (const cat of Object.values(hierarchy)) {
    for (const subcat of Object.values(cat.subcategories)) {
      subcat.niches.sort((a, b) => b.video_count - a.video_count)
    }
  }

  res.status(200).json({
    ready: true,
    stats: taxonomy.stats,
    sources: taxonomy.sources,
    approach: taxonomy.approach,
    generated_at: taxonomy.generated_at,
    evaluation: evaluation ? {
      overall_score: evaluation.scores.overall,
      scores: evaluation.scores,
      coverage: evaluation.coverage,
      niche_sizes: evaluation.niche_sizes,
      category_distribution: evaluation.category_distribution,
    } : null,
    hierarchy,
    categories: Object.entries(taxonomy.categories).map(([id, data]) => ({ id, ...data })),
  })
}
