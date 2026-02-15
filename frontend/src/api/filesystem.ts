import client from './client'
import type { FileBrowseResponse } from '@/types/project'

export const browseDirectory = async (
  path?: string
): Promise<FileBrowseResponse> => {
  const response = await client.get('/filesystem/browse', {
    params: path ? { path } : undefined,
  })
  return response.data
}
