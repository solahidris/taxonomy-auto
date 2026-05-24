import type { NextApiRequest, NextApiResponse } from 'next'
import { classifyText, loadTaxonomy } from '../../../lib/v6classify'

const YT_KEY = process.env.YOUTUBE_API_KEY
const YT_BASE = 'https://www.googleapis.com/youtube/v3'

async function ytFetch(endpoint: string, params: Record<string, string>) {
  const url = new URL(`${YT_BASE}/${endpoint}`)
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v)
  url.searchParams.set('key', YT_KEY!)
  const r = await fetch(url.toString())
  if (!r.ok) throw new Error(`YouTube API error: ${r.status}`)
  return r.json()
}

function normalizeHandle(input: string): string {
  return input
    .replace(/^https?:\/\/(www\.)?youtube\.com\/@?/, '')
    .replace(/^@/, '')
    .trim()
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end()
  if (!YT_KEY) return res.status(503).json({ error: 'YOUTUBE_API_KEY not set' })

  const { handle } = req.body as { handle?: string }
  if (!handle?.trim()) return res.status(400).json({ error: 'handle required' })

  const taxonomy = loadTaxonomy()
  if (!taxonomy) return res.status(503).json({ error: 'V6 taxonomy not ready' })

  const query = normalizeHandle(handle)

  // Step 1: Find the channel
  const channelSearch = await ytFetch('search', {
    part: 'snippet',
    type: 'channel',
    q: query,
    maxResults: '1',
  })

  if (!channelSearch.items?.length) {
    return res.status(404).json({ error: `No YouTube channel found for "${handle}"` })
  }

  const channel = channelSearch.items[0]
  const channelId: string = channel.snippet.channelId || channel.id?.channelId
  const channelTitle: string = channel.snippet.channelTitle
  const channelDescription: string = channel.snippet.description || ''
  const thumbnail: string = channel.snippet.thumbnails?.medium?.url || ''

  // Step 2: Fetch recent videos
  const videoSearch = await ytFetch('search', {
    part: 'id',
    type: 'video',
    channelId,
    maxResults: '25',
    order: 'date',
  })

  const videoIds: string[] = (videoSearch.items || [])
    .map((v: { id: { videoId: string } }) => v.id.videoId)
    .filter(Boolean)

  if (!videoIds.length) {
    return res.status(404).json({ error: 'No videos found for this channel' })
  }

  // Step 3: Fetch video details
  const videoDetails = await ytFetch('videos', {
    part: 'snippet',
    id: videoIds.join(','),
    maxResults: '25',
  })

  type VideoItem = { snippet: { title: string; description: string; tags?: string[] } }
  type Video = { title: string; description: string; tags: string[] }
  const videos: Video[] = (videoDetails.items || []).map((v: VideoItem) => ({
    title: v.snippet.title,
    description: v.snippet.description?.slice(0, 200) || '',
    tags: (v.snippet.tags || []).slice(0, 10),
  }))

  // Step 4: Aggregate into classify text
  const aggregatedText = [
    channelTitle,
    channelDescription.slice(0, 300),
    ...videos.map((v: Video) => `${v.title}. ${v.description}. ${v.tags.join(' ')}`),
  ].join('\n')

  // Step 5: Classify
  const classification = await classifyText(aggregatedText)
  if (!classification) {
    return res.status(503).json({ error: 'Classification failed' })
  }

  res.status(200).json({
    creator: {
      handle: query,
      channel_title: channelTitle,
      channel_id: channelId,
      description: channelDescription.slice(0, 300),
      thumbnail,
      videos_analyzed: videos.length,
    },
    classification,
  })
}
