import type { NextApiRequest, NextApiResponse } from 'next'
import fs from 'fs'
import path from 'path'

type Taxonomy = {
  categories: Record<number, { name: string; niche_count: number }>
  subcategories: Record<string, { name: string; category_id: number; category_name: string; niche_count: number }>
  niches: Record<string, {
    name: string
    category_id: number
    category_name: string
    subcategory_key: string
    subcategory_name: string
    video_count: number
    exemplar_creators: Array<{ channel_id: string; channel_title: string; video_count: number }>
    sample_titles: string[]
    centroid: number[]
  }>
  stats: {
    total_niches: number
    total_categories: number
    total_subcategories: number
    total_videos: number
  }
}

let cache: Taxonomy | null = null

function loadTaxonomy(): Taxonomy | null {
  if (cache) return cache
  const fp = path.join(process.cwd(), 'data', 'v1', 'taxonomy.json')
  if (!fs.existsSync(fp)) return null
  cache = JSON.parse(fs.readFileSync(fp, 'utf-8'))
  return cache
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') return res.status(405).end()

  const taxonomy = loadTaxonomy()
  if (!taxonomy) {
    return res.status(503).json({
      error: 'V1 Taxonomy not ready. Run the V1 pipeline first.',
      ready: false,
    })
  }

  // Build hierarchical structure for UI
  const hierarchy: Record<string, {
    name: string
    subcategories: Record<string, {
      name: string
      niches: Array<{
        id: string
        name: string
        video_count: number
        exemplar_creators: Array<{ channel_title: string }>
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

  // Add subcategories
  for (const [subcatKey, subcatData] of Object.entries(taxonomy.subcategories)) {
    const catId = String(subcatData.category_id)
    if (hierarchy[catId]) {
      hierarchy[catId].subcategories[subcatKey] = {
        name: subcatData.name,
        niches: []
      }
    }
  }

  // Add niches
  for (const [nicheId, nicheData] of Object.entries(taxonomy.niches)) {
    const catId = String(nicheData.category_id)
    const subcatKey = nicheData.subcategory_key

    if (hierarchy[catId]?.subcategories[subcatKey]) {
      hierarchy[catId].subcategories[subcatKey].niches.push({
        id: nicheId,
        name: nicheData.name,
        video_count: nicheData.video_count,
        exemplar_creators: nicheData.exemplar_creators.slice(0, 3).map(c => ({
          channel_title: c.channel_title
        }))
      })
    }
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
    hierarchy,
    // Also return flat lists for simpler views
    categories: Object.entries(taxonomy.categories).map(([id, data]) => ({
      id: Number(id),
      ...data
    })),
    subcategories: Object.entries(taxonomy.subcategories).map(([key, data]) => ({
      key,
      ...data
    })),
  })
}
