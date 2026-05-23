import type { NextApiRequest, NextApiResponse } from 'next'
import fs from 'fs'
import path from 'path'

type V5Niche = {
  id: string
  name: string
  description: string
  keywords: string[]
  source: 'v5_discovered'
  platforms: string[]
  video_count: number
  top_hashtags: string[]
}

type V5Category = {
  id: string
  name: string
  description: string
  source: string
  children: V5Niche[]
}

type V5Taxonomy = {
  version: string
  generated_at: string
  platforms: string[]
  approach: string
  stats: {
    v4_niches: number
    v5_new_niches: number
    cross_platform_validated: number
  }
  categories: V5Category[]
  total_niches: number
  platform_distribution: Record<string, number>
}

type V5Evaluation = {
  version: string
  metrics: {
    scale: { v5_niches: number; target: number; score: number }
    platforms: { covered: number; target: number; breakdown: Record<string, number>; score: number }
    validation: { validated_niches: number; rate_pct: number; score: number }
    discoveries: { new_niches: number; score: number }
  }
  overall_score: number
  success_criteria: Record<string, boolean>
}

let taxonomyCache: V5Taxonomy | null = null
let evaluationCache: V5Evaluation | null = null

function loadTaxonomy(): V5Taxonomy | null {
  if (taxonomyCache) return taxonomyCache
  const fp = path.join(process.cwd(), 'data', 'v5', 'taxonomy.json')
  if (!fs.existsSync(fp)) return null
  taxonomyCache = JSON.parse(fs.readFileSync(fp, 'utf-8'))
  return taxonomyCache
}

function loadEvaluation(): V5Evaluation | null {
  if (evaluationCache) return evaluationCache
  const fp = path.join(process.cwd(), 'data', 'v5', 'evaluation.json')
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
      error: 'V5 Taxonomy not ready. Run the V5 pipeline first.',
      ready: false,
    })
  }

  // Flatten niches for easy display
  const allNiches: V5Niche[] = []
  for (const category of taxonomy.categories) {
    for (const niche of category.children) {
      allNiches.push(niche)
    }
  }

  // Sort by video count
  allNiches.sort((a, b) => b.video_count - a.video_count)

  // Platform stats
  const platformStats: Record<string, { niches: number; videos: number }> = {
    tiktok: { niches: 0, videos: 0 },
    instagram: { niches: 0, videos: 0 },
    youtube: { niches: 0, videos: 0 },
  }

  for (const niche of allNiches) {
    for (const platform of niche.platforms) {
      if (platformStats[platform]) {
        platformStats[platform].niches++
        platformStats[platform].videos += niche.video_count
      }
    }
  }

  // Multi-platform niches (niches present on 2+ platforms)
  const multiPlatformNiches = allNiches.filter(n => n.platforms.length >= 2)

  // Group by dominant content category
  const contentGroups: Record<string, V5Niche[]> = {
    fitness: [],
    food: [],
    beauty: [],
    lifestyle: [],
  }

  for (const niche of allNiches) {
    const nameLower = niche.name.toLowerCase()
    const descLower = niche.description.toLowerCase()

    if (nameLower.includes('workout') || nameLower.includes('training') ||
        nameLower.includes('fitness') || nameLower.includes('yoga') ||
        nameLower.includes('running') || nameLower.includes('gym') ||
        nameLower.includes('calisthenics') || nameLower.includes('hiit')) {
      contentGroups.fitness.push(niche)
    } else if (nameLower.includes('meal') || nameLower.includes('recipe') ||
               nameLower.includes('food') || nameLower.includes('kitchen') ||
               nameLower.includes('keto') || nameLower.includes('cooking') ||
               nameLower.includes('calorie')) {
      contentGroups.food.push(niche)
    } else if (nameLower.includes('makeup') || nameLower.includes('skincare') ||
               nameLower.includes('beauty')) {
      contentGroups.beauty.push(niche)
    } else {
      contentGroups.lifestyle.push(niche)
    }
  }

  res.status(200).json({
    ready: true,
    version: taxonomy.version,
    platforms: taxonomy.platforms,
    stats: {
      total_niches: taxonomy.total_niches,
      ...taxonomy.stats,
    },
    evaluation: evaluation ? {
      overall_score: evaluation.overall_score,
      metrics: evaluation.metrics,
      success_criteria: evaluation.success_criteria,
    } : null,
    platformStats,
    multiPlatformNiches: multiPlatformNiches.length,
    contentGroups: {
      fitness: contentGroups.fitness.length,
      food: contentGroups.food.length,
      beauty: contentGroups.beauty.length,
      lifestyle: contentGroups.lifestyle.length,
    },
    niches: allNiches,
    nichesByGroup: contentGroups,
    platform_distribution: taxonomy.platform_distribution,
  })
}
