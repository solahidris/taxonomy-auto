import type { NextApiRequest, NextApiResponse } from 'next'
import fs from 'fs'
import path from 'path'

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') return res.status(405).end()

  const youtubeKey = !!(process.env.YOUTUBE_API_KEY?.trim())
  const openaiKey = !!(process.env.OPENAI_API_KEY?.trim())
  const taxonomyPath = path.join(process.cwd(), 'data', 'v6', 'taxonomy.json')
  const taxonomyReady = fs.existsSync(taxonomyPath)

  let taxonomyStats: { total_niches: number; total_categories: number; total_videos: number } | null = null
  if (taxonomyReady) {
    try {
      const raw = JSON.parse(fs.readFileSync(taxonomyPath, 'utf-8'))
      taxonomyStats = raw.stats
    } catch {}
  }

  res.status(200).json({
    keys: { youtube: youtubeKey, openai: openaiKey },
    taxonomy: { ready: taxonomyReady, stats: taxonomyStats },
    ready: youtubeKey && openaiKey && taxonomyReady,
  })
}
