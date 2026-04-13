<template>
  <div class="layout">

    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="logo">
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
          <circle cx="14" cy="14" r="13" stroke="#6366f1" stroke-width="2"/>
          <circle cx="14" cy="14" r="7" stroke="#6366f1" stroke-width="1.5" stroke-dasharray="3 2"/>
          <circle cx="14" cy="14" r="2.5" fill="#6366f1"/>
        </svg>
        <span>Radar</span>
      </div>

      <div class="section-tabs">
        <button :class="['section-tab', { active: section === 'companies' }]" @click="section = 'companies'">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
          Компании
        </button>
        <button :class="['section-tab', { active: section === 'persons' }]" @click="section = 'persons'">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          Люди
        </button>
      </div>

      <nav v-if="section === 'companies'" class="nav">
        <button v-for="c in companies" :key="c.id"
          :class="['nav-item', { active: selectedId === c.id && section === 'companies' }]"
          @click="selectedId = c.id">
          <span class="nav-dot" :style="{ background: colorFor(c.id) }"></span>
          <span class="nav-name">{{ c.name }}</span>
        </button>
        <div v-if="!companies.length" class="nav-empty">Нет компаний</div>
      </nav>

      <nav v-else class="nav">
        <button v-for="p in persons" :key="p.id"
          :class="['nav-item', { active: selectedPersonId === p.id }]"
          @click="selectedPersonId = p.id">
          <span class="nav-dot" style="background:#a78bfa"></span>
          <span class="nav-name">{{ p.last_name }} {{ p.first_name }}</span>
        </button>
        <div v-if="!persons.length" class="nav-empty">Нет людей</div>
      </nav>

      <div class="sidebar-footer">
        <button class="btn btn-primary" style="width:100%"
          @click="section === 'companies' ? (showAddCompany = true) : (showAddPerson = true)">
          + Добавить
        </button>
      </div>
    </aside>

    <!-- Main -->
    <main class="main">
      <template v-if="section === 'companies'">
        <Dashboard v-if="selectedCompany" :company="selectedCompany" @deleted="onCompanyDeleted" />
        <EmptyState v-else text="Добавь компанию для мониторинга" @add="showAddCompany = true" />
      </template>
      <template v-else>
        <PersonDashboard v-if="selectedPerson" :person="selectedPerson" @deleted="onPersonDeleted" />
        <EmptyState v-else text="Добавь человека для поиска" @add="showAddPerson = true" />
      </template>
    </main>

    <!-- Modal: компания -->
    <transition name="fade">
      <div v-if="showAddCompany" class="modal-overlay" @click.self="showAddCompany = false">
        <div class="modal">
          <h3>Новая компания</h3>
          <div class="form-group">
            <label>Название</label>
            <input v-model="companyForm.name" placeholder="Apple, Tesla, Газпром..." />
          </div>
          <div class="form-group">
            <label>Ключевые слова <span style="color:#4a5568">(через запятую)</span></label>
            <textarea v-model="companyForm.keywords" rows="3" placeholder="Apple Inc, iPhone, Tim Cook" />
          </div>
          <div class="modal-actions">
            <button class="btn btn-ghost" @click="showAddCompany = false">Отмена</button>
            <button class="btn btn-primary" :disabled="saving" @click="addCompany">
              <span v-if="saving" class="spin"></span>
              <span v-else>Добавить</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Modal: человек -->
    <transition name="fade">
      <div v-if="showAddPerson" class="modal-overlay" @click.self="showAddPerson = false">
        <div class="modal">
          <h3>Новый человек</h3>
          <div class="form-row">
            <div class="form-group">
              <label>Фамилия *</label>
              <input v-model="personForm.last_name" placeholder="Иванов" />
            </div>
            <div class="form-group">
              <label>Имя *</label>
              <input v-model="personForm.first_name" placeholder="Иван" />
            </div>
          </div>
          <div class="form-group">
            <label>Отчество</label>
            <input v-model="personForm.middle_name" placeholder="Иванович" />
          </div>
          <div class="form-group">
            <label>Дата рождения</label>
            <input v-model="personForm.birth_date" type="date" />
          </div>
          <div class="form-group">
            <label>Фото <span style="color:#4a5568">(опционально)</span></label>
            <input type="file" accept="image/*" @change="onPhotoSelect" style="padding:6px" />
            <div v-if="photoPreview" class="photo-preview">
              <img :src="photoPreview" alt="preview" />
            </div>
          </div>
          <div class="form-group">
            <label>Заметки</label>
            <input v-model="personForm.notes" placeholder="Должность, организация..." />
          </div>
          <div class="modal-actions">
            <button class="btn btn-ghost" @click="showAddPerson = false">Отмена</button>
            <button class="btn btn-primary" :disabled="saving" @click="addPerson">
              <span v-if="saving" class="spin"></span>
              <span v-else>Добавить</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from './api.js'
import Dashboard from './components/Dashboard.vue'
import PersonDashboard from './components/PersonDashboard.vue'

const EmptyState = {
  props: ['text'],
  emits: ['add'],
  template: `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:16px;color:#4a5568;font-size:14px">
      <svg width="64" height="64" viewBox="0 0 64 64" fill="none"><circle cx="32" cy="32" r="31" stroke="#2d3148" stroke-width="2"/><circle cx="32" cy="32" r="16" stroke="#2d3148" stroke-width="1.5" stroke-dasharray="4 3"/><circle cx="32" cy="32" r="5" fill="#2d3148"/></svg>
      <p>{{ text }}</p>
      <button class="btn btn-primary" @click="$emit('add')">+ Добавить</button>
    </div>
  `
}

const section          = ref('companies')
const companies        = ref([])
const persons          = ref([])
const selectedId       = ref(null)
const selectedPersonId = ref(null)
const showAddCompany   = ref(false)
const showAddPerson    = ref(false)
const saving           = ref(false)
const photoFile        = ref(null)
const photoPreview     = ref(null)

const companyForm = ref({ name: '', keywords: '' })
const personForm  = ref({ last_name: '', first_name: '', middle_name: '', birth_date: '', notes: '' })

const COLORS = ['#6366f1','#34d399','#f59e0b','#f87171','#60a5fa','#a78bfa','#fb7185']
const colorFor = id => COLORS[(id - 1) % COLORS.length]

const selectedCompany = computed(() => companies.value.find(c => c.id === selectedId.value))
const selectedPerson  = computed(() => persons.value.find(p => p.id === selectedPersonId.value))

async function loadCompanies() {
  companies.value = await api.getCompanies()
  if (!selectedId.value && companies.value.length) selectedId.value = companies.value[0].id
}

async function loadPersons() {
  persons.value = await api.getPersons()
  if (!selectedPersonId.value && persons.value.length) selectedPersonId.value = persons.value[0].id
}

async function addCompany() {
  if (!companyForm.value.name.trim()) return
  saving.value = true
  try {
    const kws = companyForm.value.keywords.split(',').map(k => k.trim()).filter(Boolean)
    const c = await api.createCompany(companyForm.value.name.trim(), kws)
    companies.value.unshift(c)
    selectedId.value = c.id
    showAddCompany.value = false
    companyForm.value = { name: '', keywords: '' }
  } finally { saving.value = false }
}

function onPhotoSelect(e) {
  const file = e.target.files[0]
  if (!file) return
  photoFile.value = file
  photoPreview.value = URL.createObjectURL(file)
}

async function addPerson() {
  if (!personForm.value.last_name.trim() || !personForm.value.first_name.trim()) return
  saving.value = true
  try {
    const fd = new FormData()
    fd.append('first_name', personForm.value.first_name.trim())
    fd.append('last_name',  personForm.value.last_name.trim())
    fd.append('middle_name', personForm.value.middle_name.trim())
    fd.append('birth_date', personForm.value.birth_date)
    fd.append('notes',      personForm.value.notes.trim())
    if (photoFile.value) fd.append('photo', photoFile.value)
    const p = await api.createPerson(fd)
    persons.value.unshift(p)
    selectedPersonId.value = p.id
    section.value = 'persons'
    showAddPerson.value = false
    personForm.value = { last_name: '', first_name: '', middle_name: '', birth_date: '', notes: '' }
    photoFile.value = null
    photoPreview.value = null
  } finally { saving.value = false }
}

function onCompanyDeleted(id) {
  companies.value = companies.value.filter(c => c.id !== id)
  selectedId.value = companies.value[0]?.id || null
}

function onPersonDeleted(id) {
  persons.value = persons.value.filter(p => p.id !== id)
  selectedPersonId.value = persons.value[0]?.id || null
}

onMounted(() => { loadCompanies(); loadPersons() })
</script>

<style scoped>
.layout { display: flex; height: 100vh; overflow: hidden; }
.sidebar {
  width: 220px; min-width: 220px;
  background: #13151f; border-right: 1px solid #2d3148;
  display: flex; flex-direction: column;
  padding: 20px 12px; gap: 16px;
}
.logo {
  display: flex; align-items: center; gap: 10px;
  padding: 0 8px; font-size: 18px; font-weight: 700;
  color: #e2e8f0; letter-spacing: -0.02em;
}
.section-tabs { display: flex; gap: 4px; }
.section-tab {
  flex: 1; display: flex; align-items: center; justify-content: center;
  gap: 5px; padding: 7px 8px; border-radius: 7px;
  background: transparent; border: 1px solid #2d3148;
  color: #64748b; font-size: 11px; font-weight: 500;
  cursor: pointer; transition: all 0.15s;
}
.section-tab:hover { color: #e2e8f0; }
.section-tab.active { background: #1e2235; color: #e2e8f0; border-color: #6366f1; }
.nav { display: flex; flex-direction: column; gap: 2px; flex: 1; overflow-y: auto; }
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 10px; border-radius: 8px;
  background: transparent; border: none;
  color: #94a3b8; font-size: 13px; font-weight: 500;
  cursor: pointer; text-align: left; transition: all 0.15s; width: 100%;
}
.nav-item:hover { background: #1e2235; color: #e2e8f0; }
.nav-item.active { background: #1e2235; color: #e2e8f0; }
.nav-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.nav-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nav-empty { color: #4a5568; font-size: 12px; padding: 8px 10px; }
.sidebar-footer { margin-top: auto; }
.main { flex: 1; overflow-y: auto; }
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.7);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal {
  background: #1a1d27; border: 1px solid #2d3148; border-radius: 14px;
  padding: 28px; width: 460px; display: flex; flex-direction: column; gap: 16px;
  max-height: 90vh; overflow-y: auto;
}
.modal h3 { font-size: 16px; font-weight: 600; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-group label { font-size: 12px; color: #94a3b8; font-weight: 500; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
.photo-preview { margin-top: 8px; }
.photo-preview img {
  width: 80px; height: 80px; border-radius: 8px;
  object-fit: cover; border: 1px solid #2d3148;
}
</style>
