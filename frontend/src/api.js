import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export default {
  // Компании
  async getCompanies()             { return (await api.get('/companies')).data },
  async createCompany(name, kws)   { return (await api.post('/companies', { name, keywords: kws })).data },
  async deleteCompany(id)          { return (await api.delete(`/companies/${id}`)).data },
  async parseMentions(id)          { return (await api.post(`/companies/${id}/parse`)).data },
  async getMentions(id, s, l=100)  { return (await api.get(`/companies/${id}/mentions`, { params: { limit: l, ...(s ? { sentiment: s } : {}) } })).data },
  async getStats(id)               { return (await api.get(`/companies/${id}/stats`)).data },

  // Люди
  async getPersons()               { return (await api.get('/persons')).data },
  async createPerson(formData)     { return (await api.post('/persons', formData, { headers: { 'Content-Type': 'multipart/form-data' } })).data },
  async deletePerson(id)           { return (await api.delete(`/persons/${id}`)).data },
  async searchPerson(id)           { return (await api.post(`/persons/${id}/search`)).data },
  async getPersonResults(id, type) { return (await api.get(`/persons/${id}/results`, { params: type ? { result_type: type } : {} })).data },
  async getPersonStats(id)         { return (await api.get(`/persons/${id}/stats`)).data },

  // Общее
  async getTaskStatus(taskId)      { return (await api.get(`/tasks/${taskId}`)).data },
}
