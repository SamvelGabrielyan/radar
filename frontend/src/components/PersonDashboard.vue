<template>
  <div class="dashboard">

    <!-- Header -->
    <div class="header">
      <div>
        <h1>{{ fullName }}</h1>
        <div class="meta-tags">
          <span v-if="person.birth_date" class="meta-tag">
            {{ formatBirthDate(person.birth_date) }}
          </span>
          <span v-if="person.notes" class="meta-tag">{{ person.notes }}</span>
        </div>
      </div>
      <div class="header-actions">
        <button class="btn btn-ghost" :disabled="searching" @click="triggerSearch">
          <span v-if="searching" class="spin"></span>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          {{ searching ? 'Поиск...' : 'Найти' }}
        </button>
        <button class="btn btn-danger" @click="remove">Удалить</button>
      </div>
    </div>

    <!-- Profile card -->
    <div class="profile-card card">
      <div class="profile-photo">
        <img v-if="person.photo_path" :src="`/api/photo/${person.id}`" alt="фото" />
        <div v-else class="photo-placeholder">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#4a5568" stroke-width="1.5">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
          </svg>
        </div>
      </div>
      <div class="profile-info">
        <div class="profile-name">{{ fullName }}</div>
        <div class="profile-details">
          <div v-if="person.birth_date" class="detail-row">
            <span class="detail-label">Дата рождения</span>
            <span class="detail-value">{{ formatBirthDate(person.birth_date) }}</span>
          </div>
          <div v-if="stats" class="detail-row">
            <span class="detail-label">Найдено упоминаний</span>
            <span class="detail-value">{{ stats.total }}</span>
          </div>
        </div>
      </div>
      <div v-if="stats?.sources" class="profile-sources">
        <div class="card-title" style="margin-bottom:12px">Источники</div>
        <div v-for="(count, src) in stats.sources" :key="src" class="source-row">
          <span class="source-name">{{ src }}</span>
          <div class="source-bar-wrap">
            <div class="source-bar" :style="{ width: barWidth(count, stats.sources) + '%' }"></div>
          </div>
          <span class="source-count">{{ count }}</span>
        </div>
      </div>
    </div>

    <!-- Results feed -->
    <div class="card results-card">
      <div class="card-header">
        <div class="card-title">Результаты поиска</div>
        <div class="filter-tabs">
          <button
            v-for="f in filters"
            :key="f.value"
            class="filter-tab"
            :class="{ active: activeFilter === f.value }"
            @click="setFilter(f.value)"
          >{{ f.label }}</button>
        </div>
      </div>

      <div v-if="loading" class="loading-center">
        <span class="spin" style="width:20px;height:20px"></span>
      </div>

      <div v-else-if="results.length" class="results-list">
        <a
          v-for="r in results"
          :key="r.id"
          :href="r.url"
          target="_blank"
          class="result-item"
        >
          <img v-if="r.image_url" :src="r.image_url" class="result-thumb" />
          <div v-else class="result-thumb-placeholder">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4a5568" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
            </svg>
          </div>
          <div class="result-body">
            <div class="result-title">{{ r.title }}</div>
            <div class="result-meta">
              <span :class="['type-badge', `type-${r.result_type}`]">{{ typeLabel(r.result_type) }}</span>
              <span class="result-dot">·</span>
              <span class="result-source">{{ r.source }}</span>
              <span class="result-dot">·</span>
              <span class="result-date">{{ formatDate(r.fetched_at) }}</span>
            </div>
            <div v-if="r.snippet" class="result-snippet">{{ r.snippet }}</div>
          </div>
          <svg class="result-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
          </svg>
        </a>
      </div>

      <div v-else class="no-data" style="padding:40px 0">
        Нажми «Найти» чтобы начать поиск по открытым источникам
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import api from '../api.js'

const props = defineProps({ person: Object })
const emit  = defineEmits(['deleted'])

const results     = ref([])
const stats       = ref(null)
const loading     = ref(false)
const searching   = ref(false)
const activeFilter = ref(null)

const filters = [
  { label: 'Все',     value: null    },
  { label: 'Новости', value: 'news'  },
  { label: 'Фото',    value: 'image' },
]

const fullName = computed(() => {
  const p = props.person
  return [p.last_name, p.first_name, p.middle_name].filter(Boolean).join(' ')
})

function typeLabel(t) {
  return { news: 'новости', image: 'фото', social: 'соцсети', registry: 'реестр' }[t] || t
}

function formatBirthDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

function barWidth(count, sources) {
  const max = Math.max(...Object.values(sources))
  return max ? Math.round((count / max) * 100) : 0
}

async function load() {
  loading.value = true
  try {
    const [s, r] = await Promise.all([
      api.getPersonStats(props.person.id),
      api.getPersonResults(props.person.id, activeFilter.value),
    ])
    stats.value   = s
    results.value = r
  } finally {
    loading.value = false
  }
}

async function setFilter(val) {
  activeFilter.value = val
  loading.value = true
  try {
    results.value = await api.getPersonResults(props.person.id, val)
  } finally {
    loading.value = false
  }
}

async function triggerSearch() {
  searching.value = true
  try {
    const { task_id } = await api.searchPerson(props.person.id)
    const poll = setInterval(async () => {
      const t = await api.getTaskStatus(task_id)
      if (t.status === 'SUCCESS' || t.status === 'FAILURE') {
        clearInterval(poll)
        searching.value = false
        await load()
      }
    }, 2000)
  } catch {
    searching.value = false
  }
}

async function remove() {
  if (!confirm(`Удалить ${fullName.value}?`)) return
  await api.deletePerson(props.person.id)
  emit('deleted', props.person.id)
}

watch(() => props.person?.id, load, { immediate: true })
</script>

<style scoped>
.dashboard { padding: 28px; display: flex; flex-direction: column; gap: 20px; }

.header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.header h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.02em; }
.meta-tags { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
.meta-tag {
  background: #1e2235; border: 1px solid #2d3148;
  border-radius: 20px; padding: 2px 10px;
  font-size: 11px; color: #94a3b8;
}
.header-actions { display: flex; gap: 8px; flex-shrink: 0; }

.profile-card {
  display: flex; align-items: flex-start; gap: 24px; flex-wrap: wrap;
}
.profile-photo {
  width: 80px; height: 80px; border-radius: 12px;
  overflow: hidden; flex-shrink: 0;
  background: #0f1117; border: 1px solid #2d3148;
  display: flex; align-items: center; justify-content: center;
}
.profile-photo img { width: 100%; height: 100%; object-fit: cover; }
.photo-placeholder { display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; }

.profile-info { flex: 1; min-width: 160px; }
.profile-name { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
.detail-row { display: flex; gap: 12px; margin-bottom: 6px; }
.detail-label { font-size: 12px; color: #64748b; min-width: 130px; }
.detail-value { font-size: 12px; color: #e2e8f0; }

.profile-sources { flex: 1; min-width: 200px; }
.card-title { font-size: 13px; font-weight: 600; color: #94a3b8; }
.source-row { display: flex; align-items: center; gap: 10px; font-size: 12px; margin-bottom: 10px; }
.source-name { color: #94a3b8; min-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.source-bar-wrap { flex: 1; height: 6px; background: #2d3148; border-radius: 3px; overflow: hidden; }
.source-bar { height: 100%; background: #a78bfa; border-radius: 3px; transition: width 0.4s; }
.source-count { color: #64748b; min-width: 24px; text-align: right; }

.results-card { display: flex; flex-direction: column; gap: 16px; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.filter-tabs { display: flex; gap: 4px; }
.filter-tab {
  padding: 5px 12px; border-radius: 6px;
  background: transparent; border: 1px solid #2d3148;
  color: #64748b; font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all 0.15s;
}
.filter-tab:hover { color: #e2e8f0; border-color: #4a5568; }
.filter-tab.active { background: #1e2235; color: #e2e8f0; border-color: #a78bfa; }

.loading-center { display: flex; justify-content: center; padding: 40px 0; }
.no-data { color: #4a5568; font-size: 13px; text-align: center; }

.results-list { display: flex; flex-direction: column; }
.result-item {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 14px 0; border-bottom: 1px solid #1e2235;
  text-decoration: none; transition: background 0.1s; cursor: pointer;
}
.result-item:last-child { border-bottom: none; }
.result-item:hover { background: #1e2235; margin: 0 -20px; padding: 14px 20px; border-radius: 8px; }

.result-thumb {
  width: 48px; height: 48px; border-radius: 8px;
  object-fit: cover; flex-shrink: 0; border: 1px solid #2d3148;
}
.result-thumb-placeholder {
  width: 48px; height: 48px; border-radius: 8px; flex-shrink: 0;
  background: #1e2235; border: 1px solid #2d3148;
  display: flex; align-items: center; justify-content: center;
}

.result-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.result-title { font-size: 13px; font-weight: 500; color: #e2e8f0; line-height: 1.4; }
.result-meta { display: flex; align-items: center; gap: 6px; font-size: 11px; flex-wrap: wrap; }
.result-dot { color: #2d3148; }
.result-source { color: #a78bfa; }
.result-date { color: #4a5568; }
.result-snippet {
  font-size: 12px; color: #64748b; line-height: 1.5;
  overflow: hidden; display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}

.type-badge {
  display: inline-flex; align-items: center;
  padding: 1px 7px; border-radius: 20px;
  font-size: 10px; font-weight: 600; letter-spacing: 0.03em;
}
.type-news    { background: #0c2340; color: #60a5fa; }
.type-image   { background: #1a0c30; color: #a78bfa; }
.type-social  { background: #0d2b1f; color: #34d399; }
.type-registry{ background: #2b1a0c; color: #f59e0b; }

.result-arrow { color: #2d3148; flex-shrink: 0; margin-top: 3px; }
</style>
