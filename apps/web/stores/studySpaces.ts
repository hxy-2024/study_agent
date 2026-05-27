import { defineStore } from 'pinia'

export interface StudySpace {
  id: string
  name: string
  goal: string
  status: string
  target_days: number
}

export const useStudySpacesStore = defineStore('studySpaces', {
  state: () => ({
    spaces: [] as StudySpace[],
    loading: false
  }),
  actions: {
    async loadSpaces() {
      const config = useRuntimeConfig()
      this.loading = true
      try {
        this.spaces = await $fetch<StudySpace[]>(`${config.public.apiBaseUrl}/study-spaces`, {
          headers: {
            'X-User-Id': '00000000-0000-0000-0000-000000000002',
            'X-Tenant-Id': '00000000-0000-0000-0000-000000000001'
          }
        })
      } finally {
        this.loading = false
      }
    }
  }
})
