import type { NextApiRequest, NextApiResponse } from 'next'
import fs from 'fs'
import path from 'path'

type Niche = {
  name: string
  description: string
  target_audience: string
  category_id: string
  category_name: string
  video_count: number
  total_views: number
  outlier_count: number
  avg_3r_scores: {
    reproducible: number
    relatable: number
    repeatable: number
  }
  exemplar_creators: Array<{
    author: string
    video_count: number
    total_views: number
    outlier_count: number
  }>
  sample_titles: string[]
  sample_hashtags: string[]
  format_types: string[]
}

type Category = {
  name: string
  cluster_count: number
  video_count: number
}

type TaxonomyData = {
  categories: Record<string, Category>
  niches: Record<string, Niche>
  stats: {
    total_categories: number
    total_niches: number
    total_videos: number
    total_views: number
    total_outliers: number
  }
}

export default function handler(
  req: NextApiRequest,
  res: NextApiResponse<TaxonomyData | { error: string }>
) {
  try {
    const dataPath = path.join(process.cwd(), 'data', 'v7', 'taxonomy.json')

    if (!fs.existsSync(dataPath)) {
      return res.status(404).json({ error: 'No taxonomy data found. Run the taxonomy pipeline first.' })
    }

    const content = fs.readFileSync(dataPath, 'utf-8')
    const taxonomy: TaxonomyData = JSON.parse(content)

    res.status(200).json(taxonomy)
  } catch (err) {
    console.error('Taxonomy API error:', err)
    res.status(500).json({ error: 'Failed to load taxonomy data' })
  }
}
