import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export default {
  // ─── Компании ──────────────────────────────────────────────────────────────
  async getCompanies()             { return (await api.get('/companies')).data },
  async createCompany(name, kws)   { return (await api.post('/companies', { name, keywords: kws })).data },
  async deleteCompany(id)          { return (await api.delete(`/companies/${id}`)).data },
  async parseMentions(id)          { return (await api.post(`/companies/${id}/parse`)).data },

  /**
   * Получает упоминания с фильтрами.
   * @param {number} id       — ID компании
   * @param {object} filters  — { sentiment, source, date_from, date_to }
   * @param {number} limit    — максимум записей
   */
  async getMentions(id, filters = {}, limit = 100) {
    const params = { limit }
    if (filters.sentiment) params.sentiment = filters.sentiment
    if (filters.source)    params.source    = filters.source
    if (filters.date_from) params.date_from = filters.date_from
    if (filters.date_to)   params.date_to   = filters.date_to
    return (await api.get(`/companies/${id}/mentions`, { params })).data
  },

  /**
   * Получает статистику, опционально за определённый период.
   */
  async getStats(id, filters = {}) {
    const params = {}
    if (filters.date_from) params.date_from = filters.date_from
    if (filters.date_to)   params.date_to   = filters.date_to
    return (await api.get(`/companies/${id}/stats`, { params })).data
  },

  // ─── Люди ──────────────────────────────────────────────────────────────────
  async getPersons()               { return (await api.get('/persons')).data },
  async createPerson(formData)     { return (await api.post('/persons', formData, { headers: { 'Content-Type': 'multipart/form-data' } })).data },
  async deletePerson(id)           { return (await api.delete(`/persons/${id}`)).data },
  async searchPerson(id)           { return (await api.post(`/persons/${id}/search`)).data },
  async getPersonResults(id, type) { return (await api.get(`/persons/${id}/results`, { params: type ? { result_type: type } : {} })).data },
  async getPersonStats(id)         { return (await api.get(`/persons/${id}/stats`)).data },

  // ─── Общее ─────────────────────────────────────────────────────────────────
  async getTaskStatus(taskId)      { return (await api.get(`/tasks/${taskId}`)).data },
}
