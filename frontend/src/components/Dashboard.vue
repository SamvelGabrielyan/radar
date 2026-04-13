<template>
  <div class="dashboard">

    <div class="header">
      <div>
        <h1>{{ company.name }}</h1>
        <div class="keywords">
          <span v-for="kw in company.keywords" :key="kw" class="kw-tag">{{ kw }}</span>
        </div>
      </div>
      <div class="header-actions">
        <button class="btn btn-ghost" :disabled="parsing" @click="triggerParse">
          <span v-if="parsing" class="spin"></span>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
          {{ parsing ? 'Парсинг...' : 'Обновить' }}
        </button>
        <button class="btn btn-danger" @click="remove">Удалить</button>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Всего упоминаний</div>
        <div class="stat-value">{{ stats?.total ?? '—' }}</div>
      </div>
      <div class="stat-card positive">
        <div class="stat-label">Позитивных</div>
        <div class="stat-value">
          {{ stats?.positive ?? '—' }}
          <span v-if="stats?.positive_pct" class="stat-pct">{{ stats.positive_pct }}%</span>
        </div>
      </div>
      <div class="stat-card neutral">
        <div class="stat-label">Нейтральных</div>
        <div class="stat-value">{{ stats?.neutral ?? '—' }}</div>
      </div>
      <div class="stat-card negative">
        <div class="stat-label">Негативных</div>
        <div class="stat-value">
          {{ stats?.negative ?? '—' }}
          <span v-if="stats?.negative_pct" class="stat-pct">{{ stats.negative_pct }}%</span>
        </div>
      </div>
    </div>

    <!-- Filters bar -->
    <div class="filters-bar card">
      <div class="filters-row">
        <div class="filter-group">
          <label class="filter-label">Тональность</label>
          <div class="filter-tabs">
            <button v-for="f in sentimentFilters" :key="f.value"
              class="filter-tab" :class="{ active: activeFilter === f.value }"
              @click="activeFilter = f.value; applyFilters()">{{ f.label }}</button>
          </div>
        </div>

        <div class="filter-group" v-if="availableSources.length">
          <label class="filter-label">Источник</label>
          <select v-model="sourceFilter" @change="applyFilters()" class="filter-select">
            <option value="">Все источники</option>
            <option v-for="s in availableSources" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>

        <div class="filter-group">
          <label class="filter-label">Период</label>
          <div class="date-range">
            <div class="date-presets">
              <button v-for="p in datePresets" :key="p.label"
                class="preset-btn" :class="{ active: activeDatePreset === p.label }"
                @click="applyDatePreset(p)">{{ p.label }}</button>
            </div>
            <div class="date-inputs">
              <input type="date" v-model="dateFrom" @change="activeDatePreset = null; applyFilters()" class="date-input" />
              <span class="date-sep">—</span>
              <input type="date" v-model="dateTo" @change="activeDatePreset = null; applyFilters()" class="date-input" />
            </div>
          </div>
        </div>

        <button v-if="hasActiveFilters" class="btn btn-ghost reset-btn" @click="resetFilters">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
          Сбросить
        </button>
      </div>
    </div>

    <div class="mid-grid">
      <div class="card chart-card">
        <div class="card-title">Тональность</div>
        <div v-if="hasData" class="chart-wrap">
          <Doughnut :data="chartData" :options="chartOptions" />
        </div>
        <div v-else class="no-data">Нет данных — запусти парсинг</div>
      </div>
      <div class="card sources-card">
        <div class="card-title">Источники</div>
        <div v-if="stats?.sources && Object.keys(stats.sources).length" class="sources-list">
          <div v-for="(count, source) in stats.sources" :key="source" class="source-row">
            <span class="source-name">{{ source }}</span>
            <div class="source-bar-wrap">
              <div class="source-bar" :style="{ width: barWidth(count) + '%' }"></div>
            </div>
            <span class="source-count">{{ count }}</span>
          </div>
        </div>
        <div v-else class="no-data">Нет данных</div>
      </div>
    </div>

    <div class="card mentions-card">
      <div class="card-header">
        <div class="card-title">
          Упоминания
          <span v-if="mentions.length" class="mention-count">{{ mentions.length }}</span>
        </div>
      </div>

      <div v-if="loading" class="mentions-loading">
        <span class="spin" style="width:20px;height:20px;border-width:2px"></span>
      </div>

      <div v-else-if="mentions.length" class="mentions-list">
        <a v-for="m in mentions" :key="m.id" :href="m.url" target="_blank" class="mention-item">
          <div class="mention-left">
            <span :class="['badge', `badge-${m.sentiment}`]">{{ sentimentLabel(m.sentiment) }}</span>
          </div>
          <div class="mention-body">
            <div class="mention-title">{{ m.title }}</div>
            <div class="mention-meta">
              <span class="mention-source">{{ m.source }}</span>
              <span class="mention-dot">·</span>
              <span class="mention-date">{{ formatDate(m.published_at || m.fetched_at) }}</span>
            </div>
            <div v-if="m.snippet" class="mention-snippet">{{ m.snippet }}</div>
          </div>
          <div class="mention-score" :class="scoreClass(m.sentiment_score)">
            {{ m.sentiment_score > 0 ? '+' : '' }}{{ m.sentiment_score.toFixed(2) }}
          </div>
        </a>
      </div>

      <div v-else class="no-data" style="padding: 40px 0">
        <template v-if="hasActiveFilters">По выбранным фильтрам ничего не найдено</template>
        <template v-else>Упоминаний не найдено — нажми «Обновить»</template>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { Doughnut } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import api from '../api.js'

ChartJS.register(ArcElement, Tooltip, Legend)

const props = defineProps({ company: Object })
const emit  = defineEmits(['deleted'])

const stats    = ref(null)
const mentions = ref([])
const loading  = ref(false)
const parsing  = ref(false)

const activeFilter     = ref(null)
const sourceFilter     = ref('')
const dateFrom         = ref('')
const dateTo           = ref('')
const activeDatePreset = ref(null)

const sentimentFilters = [
  { label: 'Все',        value: null       },
  { label: 'Позитив',    value: 'positive' },
  { label: 'Нейтрально', value: 'neutral'  },
  { label: 'Негатив',    value: 'negative' },
]

const datePresets = [
  { label: 'Сегодня', days: 0  },
  { label: '7 дней',  days: 7  },
  { label: '30 дней', days: 30 },
  { label: '90 дней', days: 90 },
]

const availableSources = computed(() => stats.value?.sources ? Object.keys(stats.value.sources) : [])
const hasActiveFilters = computed(() => activeFilter.value || sourceFilter.value || dateFrom.value || dateTo.value)
const hasData = computed(() => stats.value && stats.value.total > 0)

const chartData = computed(() => ({
  labels: ['Позитив', 'Нейтрально', 'Негатив'],
  datasets: [{
    data: [stats.value?.positive ?? 0, stats.value?.neutral ?? 0, stats.value?.negative ?? 0],
    backgroundColor: ['#059669', '#374151', '#dc2626'],
    borderColor: ['#10b981', '#4b5563', '#ef4444'],
    borderWidth: 1, hoverOffset: 6,
  }]
}))

const chartOptions = {
  responsive: true, cutout: '68%',
  plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 12 }, padding: 16 } } }
}

function barWidth(count) {
  const max = Math.max(...Object.values(stats.value?.sources || {}))
  return max ? Math.round((count / max) * 100) : 0
}
function sentimentLabel(s) { return { positive: '+ позитив', neutral: '● нейтрал', negative: '– негатив' }[s] || s }
function scoreClass(score) { return score > 0.1 ? 'score-pos' : score < -0.1 ? 'score-neg' : 'score-neu' }
function formatDate(str) {
  if (!str) return ''
  return new Date(str).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
function toISODate(d) { return d.toISOString().split('T')[0] }

function buildFilters() {
  return {
    sentiment: activeFilter.value || undefined,
    source:    sourceFilter.value || undefined,
    date_from: dateFrom.value || undefined,
    date_to:   dateTo.value || undefined,
  }
}

async function applyFilters() {
  loading.value = true
  try {
    const f = buildFilters()
    const [s, m] = await Promise.all([api.getStats(props.company.id, f), api.getMentions(props.company.id, f, 100)])
    stats.value = s
    mentions.value = m
  } catch(e) { console.error(e) }
  finally { loading.value = false }
}

function applyDatePreset(preset) {
  activeDatePreset.value = preset.label
  dateTo.value = toISODate(new Date())
  if (preset.days === 0) { dateFrom.value = toISODate(new Date()) }
  else { const from = new Date(); from.setDate(from.getDate() - preset.days); dateFrom.value = toISODate(from) }
  applyFilters()
}

function resetFilters() {
  activeFilter.value = null; sourceFilter.value = ''; dateFrom.value = ''; dateTo.value = ''; activeDatePreset.value = null
  applyFilters()
}

async function triggerParse() {
  parsing.value = true
  try {
    const { task_id } = await api.parseMentions(props.company.id)
    const poll = setInterval(async () => {
      const t = await api.getTaskStatus(task_id)
      if (t.status === 'SUCCESS' || t.status === 'FAILURE') { clearInterval(poll); parsing.value = false; await applyFilters() }
    }, 2000)
  } catch { parsing.value = false }
}

async function remove() {
  if (!confirm(`Удалить ${props.company.name}?`)) return
  await api.deleteCompany(props.company.id)
  emit('deleted', props.company.id)
}

watch(() => props.company?.id, () => {
  activeFilter.value = null; sourceFilter.value = ''; dateFrom.value = ''; dateTo.value = ''; activeDatePreset.value = null
  applyFilters()
}, { immediate: true })
</script>

<style scoped>
.dashboard { padding: 28px; display: flex; flex-direction: column; gap: 20px; }
.header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.header h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.02em; }
.keywords { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.kw-tag { background: #1e2235; border: 1px solid #2d3148; border-radius: 20px; padding: 2px 10px; font-size: 11px; color: #94a3b8; }
.header-actions { display: flex; gap: 8px; flex-shrink: 0; }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.stat-card { background: #1a1d27; border: 1px solid #2d3148; border-radius: 12px; padding: 16px 20px; }
.stat-card.positive { border-color: #064e3b; }
.stat-card.neutral  { border-color: #2d3148; }
.stat-card.negative { border-color: #7f1d1d; }
.stat-label { font-size: 12px; color: #64748b; margin-bottom: 8px; }
.stat-value { font-size: 28px; font-weight: 700; letter-spacing: -0.03em; display: flex; align-items: baseline; gap: 6px; }
.stat-pct { font-size: 13px; font-weight: 400; color: #64748b; }
.positive .stat-value { color: #34d399; }
.negative .stat-value { color: #f87171; }
.filters-bar { padding: 16px 20px; }
.filters-row { display: flex; align-items: flex-end; gap: 20px; flex-wrap: wrap; }
.filter-group { display: flex; flex-direction: column; gap: 6px; }
.filter-label { font-size: 11px; color: #64748b; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
.filter-tabs { display: flex; gap: 4px; }
.filter-tab { padding: 5px 12px; border-radius: 6px; background: transparent; border: 1px solid #2d3148; color: #64748b; font-size: 12px; font-weight: 500; cursor: pointer; transition: all 0.15s; }
.filter-tab:hover { color: #e2e8f0; border-color: #4a5568; }
.filter-tab.active { background: #1e2235; color: #e2e8f0; border-color: #6366f1; }
.filter-select { background: #0f1117; border: 1px solid #2d3148; border-radius: 6px; color: #e2e8f0; font-size: 12px; padding: 5px 10px; outline: none; cursor: pointer; min-width: 140px; }
.filter-select:focus { border-color: #6366f1; }
.date-range { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.date-presets { display: flex; gap: 4px; }
.preset-btn { padding: 5px 10px; border-radius: 6px; background: transparent; border: 1px solid #2d3148; color: #64748b; font-size: 11px; font-weight: 500; cursor: pointer; transition: all 0.15s; white-space: nowrap; }
.preset-btn:hover { color: #e2e8f0; border-color: #4a5568; }
.preset-btn.active { background: #1e2235; color: #e2e8f0; border-color: #6366f1; }
.date-inputs { display: flex; align-items: center; gap: 6px; }
.date-input { background: #0f1117; border: 1px solid #2d3148; border-radius: 6px; color: #e2e8f0; font-size: 12px; padding: 4px 8px; outline: none; width: 130px; font-family: 'Inter', sans-serif; }
.date-input:focus { border-color: #6366f1; }
.date-input::-webkit-calendar-picker-indicator { filter: invert(0.7); cursor: pointer; }
.date-sep { color: #4a5568; font-size: 12px; }
.reset-btn { padding: 5px 12px; font-size: 12px; margin-left: auto; align-self: flex-end; }
.mid-grid { display: grid; grid-template-columns: 280px 1fr; gap: 12px; }
.chart-card { display: flex; flex-direction: column; gap: 16px; }
.chart-wrap { max-width: 240px; margin: 0 auto; }
.card-title { font-size: 13px; font-weight: 600; color: #94a3b8; display: flex; align-items: center; gap: 8px; }
.mention-count { background: #1e2235; color: #6366f1; font-size: 11px; padding: 1px 7px; border-radius: 10px; }
.no-data { color: #4a5568; font-size: 13px; padding: 20px 0; text-align: center; }
.sources-list { display: flex; flex-direction: column; gap: 12px; margin-top: 4px; }
.source-row { display: flex; align-items: center; gap: 10px; font-size: 12px; }
.source-name { color: #94a3b8; min-width: 130px; }
.source-bar-wrap { flex: 1; height: 6px; background: #2d3148; border-radius: 3px; overflow: hidden; }
.source-bar { height: 100%; background: #6366f1; border-radius: 3px; transition: width 0.4s; }
.source-count { color: #64748b; min-width: 28px; text-align: right; }
.mentions-card { display: flex; flex-direction: column; gap: 16px; }
.card-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.mentions-loading { display: flex; justify-content: center; padding: 40px 0; }
.mentions-list { display: flex; flex-direction: column; gap: 0; }
.mention-item { display: flex; align-items: flex-start; gap: 14px; padding: 14px 0; border-bottom: 1px solid #1e2235; text-decoration: none; transition: background 0.1s; cursor: pointer; }
.mention-item:last-child { border-bottom: none; }
.mention-item:hover { background: #1e2235; margin: 0 -20px; padding: 14px 20px; border-radius: 8px; }
.mention-left { padding-top: 2px; flex-shrink: 0; }
.mention-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.mention-title { font-size: 13px; font-weight: 500; color: #e2e8f0; line-height: 1.4; }
.mention-meta { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #4a5568; }
.mention-source { color: #6366f1; }
.mention-dot { color: #2d3148; }
.mention-snippet { font-size: 12px; color: #64748b; line-height: 1.5; margin-top: 2px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.mention-score { font-size: 12px; font-weight: 600; flex-shrink: 0; padding-top: 2px; min-width: 40px; text-align: right; }
.score-pos { color: #34d399; }
.score-neg { color: #f87171; }
.score-neu { color: #64748b; }
</style>
