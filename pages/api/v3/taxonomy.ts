import type { NextApiRequest, NextApiResponse } from 'next'
import fs from 'fs'
import path from 'path'

type SubNiche = {
  id: string
  name: string
  description: string
  source: 'llm_generated'
  confidence: string
  validation_status: 'validated' | 'partial' | 'unvalidated'
  video_support: number
  parent_niche_id: string
  parent_niche_name: string
  category_name: string
  subcategory_name: string
  target_audience?: string
  validation_keywords: string[]
  expected_hashtags: string[]
  matched_terms: string[]
}

type V3Taxonomy = {
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
    has_sub_niches: boolean
    sub_niche_ids: string[]
    centroid?: number[]
  }>
  sub_niches: Record<string, SubNiche>
  stats: {
    total_niches: number
    v1_embedding_niches: number
    v2_hashtag_niches: number
    v3_llm_sub_niches: number
    validated_sub_niches: number
    partial_sub_niches: number
    total_categories: number
    total_subcategories: number
  }
  hierarchy?: Record<string, {
    name: string
    subcategories: Record<string, {
      name: string
      niches: Array<{
        id: string
        name: string
        video_count: number
        source: string
        has_sub_niches: boolean
        sub_niche_count: number
      }>
    }>
  }>
}

type V3Evaluation = {
  v2_metrics: { name: string; total_niches: number; total_categories: number }
  v3_metrics: {
    name: string
    total_niches: number
    main_niches: number
    sub_niches: number
    total_categories: number
    approaches: string[]
  }
  comparison: {
    v2_niches: number
    v3_niches: number
    new_in_v3: number
    growth_pct: number
    niches_with_sub_niches: number
  }
  source_distribution: Record<string, number>
  llm_quality: {
    total_suggestions: number
    validated: number
    partial: number
    unvalidated: number
    validation_rate: number
    strict_validation_rate: number
  }
  specificity: {
    specific_niches: number
    generic_niches: number
    specificity_rate: number
  }
  success_criteria: Record<string, boolean>
  overall_score: number
  score_breakdown: Record<string, number>
}

let taxonomyCache: V3Taxonomy | null = null
let evaluationCache: V3Evaluation | null = null

function loadTaxonomy(): V3Taxonomy | null {
  if (taxonomyCache) return taxonomyCache
  const fp = path.join(process.cwd(), 'data', 'v3', 'taxonomy.json')
  if (!fs.existsSync(fp)) return null
  taxonomyCache = JSON.parse(fs.readFileSync(fp, 'utf-8'))
  return taxonomyCache
}

function loadEvaluation(): V3Evaluation | null {
  if (evaluationCache) return evaluationCache
  const fp = path.join(process.cwd(), 'data', 'v3', 'evaluation.json')
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
      error: 'V3 Taxonomy not ready. Run the V3 pipeline first.',
      ready: false,
    })
  }

  // Get LLM-generated sub-niches
  const llmSubNiches = Object.entries(taxonomy.sub_niches)
    .map(([id, sub]) => ({
      id,
      name: sub.name,
      description: sub.description,
      validation_status: sub.validation_status,
      video_support: sub.video_support,
      parent_niche_id: sub.parent_niche_id,
      parent_niche_name: sub.parent_niche_name,
      category_name: sub.category_name,
      matched_terms: sub.matched_terms,
    }))
    .sort((a, b) => b.video_support - a.video_support)

  // Get niches that have sub-niches
  const nichesWithSubs = Object.entries(taxonomy.niches)
    .filter(([_, n]) => n.has_sub_niches)
    .map(([id, n]) => ({
      id,
      name: n.name,
      sub_niche_count: n.sub_niche_ids.length,
      sub_niches: n.sub_niche_ids.map(subId => ({
        id: subId,
        name: taxonomy.sub_niches[subId]?.name || 'Unknown',
        validation_status: taxonomy.sub_niches[subId]?.validation_status || 'unknown',
        video_support: taxonomy.sub_niches[subId]?.video_support || 0,
      })),
    }))
    .sort((a, b) => b.sub_niche_count - a.sub_niche_count)

  // Build hierarchical structure for UI - enhanced with sub-niches
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
        has_sub_niches: boolean
        sub_niches: Array<{
          id: string
          name: string
          validation_status: string
          video_support: number
        }>
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
    if (!catId) catId = 'cat_hashtag'

    if (!hierarchy[catId]) {
      hierarchy[catId] = { name: catName, subcategories: {} }
    }

    const subcatKey = `${catId}_${subcatName.replace(/\s+/g, '_').toLowerCase()}`
    if (!hierarchy[catId].subcategories[subcatKey]) {
      hierarchy[catId].subcategories[subcatKey] = { name: subcatName, niches: [] }
    }

    // Get sub-niches for this niche
    const subNiches = nicheData.sub_niche_ids.map(subId => ({
      id: subId,
      name: taxonomy.sub_niches[subId]?.name || 'Unknown',
      validation_status: taxonomy.sub_niches[subId]?.validation_status || 'unknown',
      video_support: taxonomy.sub_niches[subId]?.video_support || 0,
    }))

    hierarchy[catId].subcategories[subcatKey].niches.push({
      id: nicheId,
      name: nicheData.name,
      video_count: nicheData.video_count,
      source: nicheData.source,
      top_hashtags: nicheData.top_hashtags || [],
      has_sub_niches: nicheData.has_sub_niches,
      sub_niches: subNiches,
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
      llm_quality: evaluation.llm_quality,
      specificity: evaluation.specificity,
      source_distribution: evaluation.source_distribution,
      success_criteria: evaluation.success_criteria,
    } : null,
    llmSubNiches,
    nichesWithSubs,
    hierarchy,
    categories: Object.entries(taxonomy.categories).map(([id, data]) => ({
      id,
      ...data
    })),
  })
}
