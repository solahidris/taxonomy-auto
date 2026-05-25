import type { NextApiRequest, NextApiResponse } from 'next'
import fs from 'fs'
import path from 'path'

type Video = {
  video_id: string
  author: string
  follower_count: number
  engagement: {
    views: number
    likes: number
    comments: number
    shares: number
  }
  subtitle: {
    transcript: string
  }
  view_follower_ratio: number
  is_outlier: boolean
  outlier_type: string | null
  expected_views: number
  view_multiplier: number
}

type AnalyticsData = {
  total_videos: number
  outlier_count: number
  correlation: number
  ratio_stats: {
    min: number
    max: number
    mean: number
    median: number
    p25: number
    p75: number
    upper_fence: number
  }
  follower_stats: {
    min: number
    max: number
    avg: number
  }
  view_stats: {
    min: number
    max: number
    avg: number
  }
  outliers: Array<{
    author: string
    video_id: string
    views: number
    followers: number
    ratio: number
    multiplier: number
    transcript_preview: string
  }>
  normal_videos: Array<{
    author: string
    video_id: string
    views: number
    followers: number
    ratio: number
    multiplier: number
  }>
  scatter_data: Array<{
    author: string
    video_id: string
    followers: number
    views: number
    ratio: number
    is_outlier: boolean
    multiplier: number
  }>
}

export default function handler(
  req: NextApiRequest,
  res: NextApiResponse<AnalyticsData | { error: string }>
) {
  try {
    const dataPath = path.join(process.cwd(), 'data', 'v7', 'raw_videos.jsonl')

    if (!fs.existsSync(dataPath)) {
      return res.status(404).json({ error: 'No V7 data found. Run the pipeline first.' })
    }

    const content = fs.readFileSync(dataPath, 'utf-8')
    const videos: Video[] = content.trim().split('\n').map(line => JSON.parse(line))

    if (videos.length === 0) {
      return res.status(404).json({ error: 'No valid data points found' })
    }

    // Calculate stats
    const n = videos.length
    const followers = videos.map(v => v.follower_count)
    const views = videos.map(v => v.engagement.views)
    const ratios = videos.map(v => v.view_follower_ratio)

    // Pearson correlation
    const meanF = followers.reduce((a, b) => a + b, 0) / n
    const meanV = views.reduce((a, b) => a + b, 0) / n

    let numerator = 0
    let denomF = 0
    let denomV = 0
    for (let i = 0; i < n; i++) {
      const diffF = followers[i] - meanF
      const diffV = views[i] - meanV
      numerator += diffF * diffV
      denomF += diffF * diffF
      denomV += diffV * diffV
    }
    const correlation = numerator / (Math.sqrt(denomF) * Math.sqrt(denomV))

    // Percentiles
    const sortedRatios = [...ratios].sort((a, b) => a - b)
    const median = sortedRatios[Math.floor(n / 2)]
    const p25 = sortedRatios[Math.floor(n * 0.25)]
    const p75 = sortedRatios[Math.floor(n * 0.75)]
    const iqr = p75 - p25
    const upperFence = p75 + 1.5 * iqr

    // Separate outliers and normal videos
    const outlierVideos = videos.filter(v => v.is_outlier)
    const normalVideos = videos.filter(v => !v.is_outlier)

    // Sort outliers by ratio descending
    outlierVideos.sort((a, b) => b.view_follower_ratio - a.view_follower_ratio)
    normalVideos.sort((a, b) => b.view_follower_ratio - a.view_follower_ratio)

    const analytics: AnalyticsData = {
      total_videos: n,
      outlier_count: outlierVideos.length,
      correlation: Math.round(correlation * 1000) / 1000,
      ratio_stats: {
        min: Math.round(Math.min(...ratios) * 10000) / 10000,
        max: Math.round(Math.max(...ratios) * 100) / 100,
        mean: Math.round(ratios.reduce((a, b) => a + b, 0) / n * 100) / 100,
        median: Math.round(median * 100) / 100,
        p25: Math.round(p25 * 100) / 100,
        p75: Math.round(p75 * 100) / 100,
        upper_fence: Math.round(upperFence * 100) / 100,
      },
      follower_stats: {
        min: Math.min(...followers),
        max: Math.max(...followers),
        avg: Math.round(followers.reduce((a, b) => a + b, 0) / n),
      },
      view_stats: {
        min: Math.min(...views),
        max: Math.max(...views),
        avg: Math.round(views.reduce((a, b) => a + b, 0) / n),
      },
      outliers: outlierVideos.slice(0, 20).map(v => ({
        author: v.author,
        video_id: v.video_id,
        views: v.engagement.views,
        followers: v.follower_count,
        ratio: Math.round(v.view_follower_ratio * 100) / 100,
        multiplier: v.view_multiplier,
        transcript_preview: v.subtitle?.transcript?.slice(0, 150) + (v.subtitle?.transcript?.length > 150 ? '...' : '') || '',
      })),
      normal_videos: normalVideos.slice(0, 10).map(v => ({
        author: v.author,
        video_id: v.video_id,
        views: v.engagement.views,
        followers: v.follower_count,
        ratio: Math.round(v.view_follower_ratio * 100) / 100,
        multiplier: v.view_multiplier,
      })),
      scatter_data: videos.map(v => ({
        author: v.author,
        video_id: v.video_id,
        followers: v.follower_count,
        views: v.engagement.views,
        ratio: Math.round(v.view_follower_ratio * 100) / 100,
        is_outlier: v.is_outlier,
        multiplier: v.view_multiplier,
      })),
    }

    res.status(200).json(analytics)
  } catch (err) {
    console.error('Analytics error:', err)
    res.status(500).json({ error: 'Failed to compute analytics' })
  }
}
