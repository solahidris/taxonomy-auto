import { NextApiRequest, NextApiResponse } from 'next'
import fs from 'fs'
import path from 'path'

type Classification = 'EVERGREEN' | 'TREND' | 'CALENDAR' | 'MOMENT' | 'UNKNOWN'

type Video = {
  id: string
  title: string
  hashtags: Array<{ name: string } | string>
  author: string
  views: number
  likes: number
  seed_keyword: string
  classification: Classification
  reason: string
}

type SeasonalData = {
  metadata: {
    total_videos: number
    min_views_threshold: number
    evergreen_count: number
    trend_count: number
    calendar_count: number
    moment_count: number
    unknown_count: number
    evergreen_pct: number
    trend_pct: number
    calendar_pct: number
    moment_pct: number
  }
  videos: Video[]
}

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    const dataPath = path.join(process.cwd(), 'data', 'v7', 'seasonal_classification.json')

    if (!fs.existsSync(dataPath)) {
      return res.status(404).json({
        error: 'Classification data not found',
        message: 'Run pipeline/v7/1_classify_seasonal.py first'
      })
    }

    const data: SeasonalData = JSON.parse(fs.readFileSync(dataPath, 'utf-8'))

    // Support filtering
    const { filter, limit, seed_keyword } = req.query

    let videos = data.videos

    // Filter by classification type
    if (filter && typeof filter === 'string') {
      videos = videos.filter(v => v.classification === filter.toUpperCase())
    }

    // Filter by seed keyword
    if (seed_keyword && typeof seed_keyword === 'string') {
      videos = videos.filter(v => v.seed_keyword === seed_keyword)
    }

    // Sort by views descending
    videos = videos.sort((a, b) => b.views - a.views)

    // Limit results
    if (limit && typeof limit === 'string') {
      videos = videos.slice(0, parseInt(limit, 10))
    }

    // Get breakdown by seed keyword
    const byKeyword: Record<string, { evergreen: number; trend: number; calendar: number; moment: number; unknown: number }> = {}
    for (const video of data.videos) {
      const kw = video.seed_keyword || 'unknown'
      if (!byKeyword[kw]) {
        byKeyword[kw] = { evergreen: 0, trend: 0, calendar: 0, moment: 0, unknown: 0 }
      }
      if (video.classification === 'EVERGREEN') byKeyword[kw].evergreen++
      else if (video.classification === 'TREND') byKeyword[kw].trend++
      else if (video.classification === 'CALENDAR') byKeyword[kw].calendar++
      else if (video.classification === 'MOMENT') byKeyword[kw].moment++
      else byKeyword[kw].unknown++
    }

    return res.status(200).json({
      metadata: data.metadata,
      by_keyword: byKeyword,
      videos
    })
  } catch (error) {
    console.error('Error loading seasonal data:', error)
    return res.status(500).json({ error: 'Failed to load classification data' })
  }
}
