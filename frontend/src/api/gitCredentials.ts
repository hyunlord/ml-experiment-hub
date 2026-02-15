import client from './client'
import type {
  GitCredentialCreate,
  GitCredentialResponse,
  GitCredentialListResponse,
} from '@/types/project'

export const getGitCredentials =
  async (): Promise<GitCredentialListResponse> => {
    const response = await client.get('/settings/git-credentials')
    return response.data
  }

export const createGitCredential = async (
  data: GitCredentialCreate
): Promise<GitCredentialResponse> => {
  const response = await client.post('/settings/git-credentials', data)
  return response.data
}

export const deleteGitCredential = async (id: number): Promise<void> => {
  await client.delete(`/settings/git-credentials/${id}`)
}
