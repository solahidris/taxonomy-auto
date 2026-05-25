import { NextApiRequest, NextApiResponse } from 'next'
import fs from 'fs'
import path from 'path'

type ThreeRScore = 1 | 2 | 3 | 4 | 5

type Reproducible = {
  score: ThreeRScore
  production_complexity: 'LOW' | 'MEDIUM' | 'HIGH'
  requires_special_access: boolean
  format_type: string
  reason: string
}

type Relatable = {
  score: ThreeRScore
  core_topic: string
  appeal_type: 'PERSONALITY_DRIVEN' | 'TOPIC_DRIVEN'
  target_industries: string[]
  reason: string
}

type Repeatable = {
  score: ThreeRScore
  format_is_common: boolean
  trend_dependent: boolean
  series_potential: string
  reason: string
}

type ThreeRClassification = {
  reproducible: Reproducible
  relatable: Relatable
  repeatable: Repeatable
}

type Seasonal = {
  seasonal_type: 'EVERGREEN' | 'SEASONAL' | 'TREND'
  confidence: number
  reason: string
  time_relevance: 'always' | 'specific_season' | 'short_window'
}

type Video = {
  video_id: string
  url: string
  bucket: 'short' | 'super_short'
  duration_seconds: number
  title: string
  hashtags: string[]
  author: string
  engagement: {
    views: number
    likes: number
    comments: number
    shares: number
  }
  subtitle: {
    available: boolean
    language: string
    transcript: string | null
  }
  classification_3r: ThreeRClassification | null
  seasonal: Seasonal | null
}

type ThreeRData = {
  metadata: {
    total_videos: number
    classified: number
    errors: number
    avg_scores: {
      reproducible: number
      relatable: number
      repeatable: number
    }
    by_bucket: {
      short: { count: number; avg_r1: number; avg_r2: number; avg_r3: number }
      super_short: { count: number; avg_r1: number; avg_r2: number; avg_r3: number }
    }
  }
  videos: Video[]
}

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    // Try to load the file with seasonal data first, fall back to just 3R
    let dataPath = path.join(process.cwd(), 'data', 'v7', '3r_seasonal_classification.json')
    if (!fs.existsSync(dataPath)) {
      dataPath = path.join(process.cwd(), 'data', 'v7', '3r_classification.json')
    }

    if (!fs.existsSync(dataPath)) {
      return res.status(404).json({
        error: 'Classification data not found',
        message: 'Run pipeline/v7/3_classify_3r.py first'
      })
    }

    const data: ThreeRData = JSON.parse(fs.readFileSync(dataPath, 'utf-8'))

    // Support filtering
    const { bucket, min_r1, min_r2, min_r3, limit, format_type, production_complexity } = req.query

    let videos = data.videos.filter(v => v.classification_3r !== null)

    // Filter by bucket
    if (bucket && typeof bucket === 'string') {
      videos = videos.filter(v => v.bucket === bucket)
    }

    // Filter by minimum scores
    if (min_r1 && typeof min_r1 === 'string') {
      const minScore = parseInt(min_r1, 10)
      videos = videos.filter(v => (v.classification_3r?.reproducible.score ?? 0) >= minScore)
    }

    if (min_r2 && typeof min_r2 === 'string') {
      const minScore = parseInt(min_r2, 10)
      videos = videos.filter(v => (v.classification_3r?.relatable.score ?? 0) >= minScore)
    }

    if (min_r3 && typeof min_r3 === 'string') {
      const minScore = parseInt(min_r3, 10)
      videos = videos.filter(v => (v.classification_3r?.repeatable.score ?? 0) >= minScore)
    }

    // Filter by format type
    if (format_type && typeof format_type === 'string') {
      videos = videos.filter(v => v.classification_3r?.reproducible.format_type === format_type)
    }

    // Filter by production complexity
    if (production_complexity && typeof production_complexity === 'string') {
      videos = videos.filter(v => v.classification_3r?.reproducible.production_complexity === production_complexity.toUpperCase())
    }

    // Sort by total 3R score (sum of all three)
    videos = videos.sort((a, b) => {
      const aScore = (a.classification_3r?.reproducible.score ?? 0) +
                     (a.classification_3r?.relatable.score ?? 0) +
                     (a.classification_3r?.repeatable.score ?? 0)
      const bScore = (b.classification_3r?.reproducible.score ?? 0) +
                     (b.classification_3r?.relatable.score ?? 0) +
                     (b.classification_3r?.repeatable.score ?? 0)
      return bScore - aScore
    })

    // Limit results
    if (limit && typeof limit === 'string') {
      videos = videos.slice(0, parseInt(limit, 10))
    }

    // Calculate format type distribution
    const formatTypes: Record<string, number> = {}
    const productionComplexity: Record<string, number> = { LOW: 0, MEDIUM: 0, HIGH: 0 }
    const appealTypes: Record<string, number> = { PERSONALITY_DRIVEN: 0, TOPIC_DRIVEN: 0 }

    for (const video of data.videos) {
      if (video.classification_3r) {
        const ft = video.classification_3r.reproducible.format_type
        formatTypes[ft] = (formatTypes[ft] || 0) + 1

        const pc = video.classification_3r.reproducible.production_complexity
        productionComplexity[pc] = (productionComplexity[pc] || 0) + 1

        const at = video.classification_3r.relatable.appeal_type
        appealTypes[at] = (appealTypes[at] || 0) + 1
      }
    }

    // Get score distribution
    const scoreDistribution = {
      reproducible: { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 },
      relatable: { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 },
      repeatable: { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 },
    }

    for (const video of data.videos) {
      if (video.classification_3r) {
        const r1 = video.classification_3r.reproducible.score
        const r2 = video.classification_3r.relatable.score
        const r3 = video.classification_3r.repeatable.score
        scoreDistribution.reproducible[r1]++
        scoreDistribution.relatable[r2]++
        scoreDistribution.repeatable[r3]++
      }
    }

    return res.status(200).json({
      metadata: data.metadata,
      distributions: {
        format_types: formatTypes,
        production_complexity: productionComplexity,
        appeal_types: appealTypes,
        scores: scoreDistribution,
      },
      videos
    })
  } catch (error) {
    console.error('Error loading 3R data:', error)
    return res.status(500).json({ error: 'Failed to load classification data' })
  }
}
