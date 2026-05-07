<script setup>
import { ref, computed, onMounted, watch } from 'vue'

const STORAGE_KEY = 'copilot-api-key'
const apiKey = ref(localStorage.getItem(STORAGE_KEY) || '')
const baseUrl = computed(() => window.location.origin)

const usage = ref(null)
const tokenInfo = ref(null)
const models = ref([])
const loading = ref(false)
const error = ref('')
const toast = ref(null)

const search = ref('')
const owners = ref(new Set())
const ownerFilter = ref('all')
const usageTab = ref('curl')
const codeBlock = ref(null)

const filteredModels = computed(() => {
  let arr = models.value
  if (ownerFilter.value !== 'all') {
    arr = arr.filter(m => (m.owned_by || '-') === ownerFilter.value)
  }
  if (search.value.trim()) {
    const q = search.value.trim().toLowerCase()
    arr = arr.filter(m =>
      (m.id || '').toLowerCase().includes(q) ||
      (m.display_name || '').toLowerCase().includes(q) ||
      (m.owned_by || '').toLowerCase().includes(q)
    )
  }
  return arr
})

const ownerList = computed(() => Array.from(owners.value).sort())

watch(apiKey, v => {
  if (v) localStorage.setItem(STORAGE_KEY, v)
  else localStorage.removeItem(STORAGE_KEY)
})

const tokenCaps = computed(() => {
  if (!tokenInfo.value?.token) return []
  const tok = tokenInfo.value.token
  const flags = []
  const map = {
    chat: 'Chat',
    cit: 'Code Insertion',
    malfil: 'Multi-line Fill',
    editor_preview_features: 'Editor Preview',
    agent_mode: 'Agent Mode',
    agent_mode_auto_approval: 'Auto Approve',
    mcp: 'MCP',
    rt: 'Rate-tier',
    '8kp': '8K Pad',
    ccr: 'CCR'
  }
  for (const [k, v] of Object.entries(map)) {
    const re = new RegExp(`(?:^|;)${k}=([^;]+)`)
    const m = tok.match(re)
    if (m && m[1] === '1') flags.push(v)
  }
  return flags
})

const tokenExpiry = computed(() => {
  if (!tokenInfo.value?.token) return null
  const m = tokenInfo.value.token.match(/exp=(\d+)/)
  if (!m) return null
  const expDate = new Date(parseInt(m[1]) * 1000)
  const now = Date.now()
  const remainMin = Math.max(0, Math.round((expDate.getTime() - now) / 60000))
  return { expDate, remainMin }
})

const tokenSku = computed(() => {
  const m = tokenInfo.value?.token?.match(/sku=([^;]+)/)
  return m ? m[1] : null
})

async function callApi(path) {
  const res = await fetch(path, {
    headers: { 'Authorization': `Bearer ${apiKey.value}` }
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`)
  }
  return await res.json()
}

async function load() {
  if (!apiKey.value) return
  loading.value = true
  error.value = ''
  try {
    const [u, t, m] = await Promise.all([
      callApi('/usage').catch(e => ({ __error: e.message })),
      callApi('/token').catch(e => ({ __error: e.message })),
      callApi('/v1/models').catch(e => ({ __error: e.message }))
    ])
    if (u.__error && t.__error && m.__error) {
      error.value = u.__error || t.__error || m.__error
      return
    }
    usage.value = u.__error ? null : u
    tokenInfo.value = t.__error ? null : t
    models.value = m.__error ? [] : (m.data || [])
    owners.value = new Set(models.value.map(x => x.owned_by || '-'))
    showToast('成功加载', 'success')
  } catch (e) {
    error.value = String(e.message || e)
    showToast(error.value, 'error')
  } finally {
    loading.value = false
  }
}

function showToast(msg, type = 'success') {
  toast.value = { msg, type }
  setTimeout(() => { toast.value = null }, 2200)
}

const copiedKey = ref(null)
async function copy(text, key) {
  try {
    await navigator.clipboard.writeText(text)
    copiedKey.value = key
    setTimeout(() => { if (copiedKey.value === key) copiedKey.value = null }, 1500)
    showToast('已复制', 'success')
  } catch {
    showToast('复制失败', 'error')
  }
}

function formatDate(d) {
  if (!d) return '-'
  if (typeof d === 'string') d = new Date(d)
  return d.toLocaleString('zh-CN', { hour12: false })
}

function logout() {
  apiKey.value = ''
  usage.value = null
  tokenInfo.value = null
  models.value = []
  owners.value = new Set()
}

onMounted(() => { if (apiKey.value) load() })

const codeSnippets = computed(() => {
  const url = baseUrl.value
  const key = apiKey.value || 'YOUR_API_KEY'
  return {
    curl: `curl ${url}/v1/chat/completions \\
  -H "Authorization: Bearer ${key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "gpt-4.1",
    "messages": [{"role":"user","content":"hello"}]
  }'`,
    python: `from openai import OpenAI

client = OpenAI(
    base_url="${url}/v1",
    api_key="${key}",
)

resp = client.chat.completions.create(
    model="gpt-4.1",
    messages=[{"role": "user", "content": "hello"}],
)
print(resp.choices[0].message.content)`,
    node: `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "${url}/v1",
  apiKey: "${key}",
});

const r = await client.chat.completions.create({
  model: "gpt-4.1",
  messages: [{ role: "user", content: "hello" }],
});
console.log(r.choices[0].message.content);`,
    cherry: `Cherry Studio / NextChat / OpenWebUI 等
─────────────────────────────────────
API 类型 / Provider:  OpenAI
API Base / Endpoint:  ${url}/v1
API Key:              ${key}
Model:                gpt-4.1（或任意已列出的模型）`
  }
})
</script>

<template>
  <div class="container">
    <header>
      <h1>
        🤖 Copilot API Dashboard
        <span class="badge">PROXY</span>
      </h1>
      <div class="key-input">
        <input
          v-model="apiKey"
          type="password"
          placeholder="API Key (Bearer token)"
          @keyup.enter="load"
        />
        <button class="btn" :disabled="!apiKey || loading" @click="load">
          {{ loading ? '加载中…' : (usage || models.length ? '刷新' : '加载') }}
        </button>
        <button v-if="apiKey" class="btn secondary" @click="logout">登出</button>
      </div>
    </header>

    <div v-if="!apiKey" class="card empty">
      <p>👋 请在右上角输入你的 API Key 后点击「加载」</p>
      <p style="font-size: 12px; margin-top: 12px;">Key 仅保存在浏览器本地（localStorage）</p>
    </div>

    <div v-if="error && apiKey" class="card" style="border-color: var(--red); color: var(--red);">
      ❌ {{ error }}
    </div>

    <!-- Top: Subscription + Quota -->
    <div v-if="usage" class="grid">
      <div class="card">
        <h2><span class="dot"></span>订阅信息</h2>
        <div class="kv">
          <div class="k">GitHub 用户</div>
          <div class="v"><code>{{ usage.login }}</code></div>
          <div class="k">Plan</div>
          <div class="v"><span class="tag blue">{{ usage.copilot_plan }}</span></div>
          <div class="k">SKU</div>
          <div class="v"><code>{{ usage.access_type_sku }}</code></div>
          <div class="k">Chat 启用</div>
          <div class="v">
            <span class="tag" :class="usage.chat_enabled ? 'green' : 'gray'">
              {{ usage.chat_enabled ? 'YES' : 'NO' }}
            </span>
          </div>
          <div class="k">MCP 启用</div>
          <div class="v">
            <span class="tag" :class="usage.is_mcp_enabled ? 'green' : 'gray'">
              {{ usage.is_mcp_enabled ? 'YES' : 'NO' }}
            </span>
          </div>
          <div class="k">分配日期</div>
          <div class="v">{{ formatDate(usage.assigned_date) }}</div>
          <div class="k">配额重置</div>
          <div class="v">{{ usage.quota_reset_date }}</div>
        </div>
      </div>

      <div class="card">
        <h2><span class="dot"></span>配额（Quota）</h2>
        <div class="quota-grid">
          <div class="quota-item">
            <div class="label">Chat</div>
            <div class="value">
              <template v-if="usage.quota_snapshots.chat.unlimited">∞</template>
              <template v-else>{{ usage.quota_snapshots.chat.percent_remaining }}%</template>
            </div>
            <div class="sub">
              <template v-if="usage.quota_snapshots.chat.unlimited">无限</template>
              <template v-else>剩余 {{ usage.quota_snapshots.chat.quota_remaining }} / {{ usage.quota_snapshots.chat.entitlement || '?' }}</template>
            </div>
            <div v-if="!usage.quota_snapshots.chat.unlimited" class="quota-bar">
              <div class="fill" :class="{
                low: usage.quota_snapshots.chat.percent_remaining < 50,
                crit: usage.quota_snapshots.chat.percent_remaining < 20
              }" :style="{ width: usage.quota_snapshots.chat.percent_remaining + '%' }"></div>
            </div>
          </div>
          <div class="quota-item">
            <div class="label">Completions</div>
            <div class="value">
              <template v-if="usage.quota_snapshots.completions.unlimited">∞</template>
              <template v-else>{{ usage.quota_snapshots.completions.percent_remaining }}%</template>
            </div>
            <div class="sub">
              <template v-if="usage.quota_snapshots.completions.unlimited">无限</template>
              <template v-else>剩余 {{ usage.quota_snapshots.completions.quota_remaining }} / {{ usage.quota_snapshots.completions.entitlement || '?' }}</template>
            </div>
            <div v-if="!usage.quota_snapshots.completions.unlimited" class="quota-bar">
              <div class="fill" :class="{
                low: usage.quota_snapshots.completions.percent_remaining < 50,
                crit: usage.quota_snapshots.completions.percent_remaining < 20
              }" :style="{ width: usage.quota_snapshots.completions.percent_remaining + '%' }"></div>
            </div>
          </div>
        </div>
        <p style="margin-top: 12px; font-size: 11px; color: var(--text-dim);">
          quota 数据来源：GitHub Copilot 订阅服务 ；下次重置 {{ usage.quota_reset_date }}
        </p>
      </div>
    </div>

    <!-- Token + API Key -->
    <div v-if="apiKey" class="grid">
      <div class="card">
        <h2><span class="dot"></span>API Key</h2>
        <div class="copy-row" style="margin-bottom: 8px;">
          <span class="text">{{ apiKey }}</span>
          <button class="copy-btn" :class="{ copied: copiedKey === 'key' }" @click="copy(apiKey, 'key')">
            {{ copiedKey === 'key' ? '✓' : '📋' }}
          </button>
        </div>
        <div class="kv" style="font-size: 12px;">
          <div class="k">使用方式</div>
          <div class="v"><code>Authorization: Bearer &lt;key&gt;</code></div>
          <div class="k">存储位置</div>
          <div class="v">localStorage（仅本浏览器）</div>
        </div>
      </div>

      <div v-if="tokenInfo?.token" class="card">
        <h2><span class="dot"></span>GitHub Copilot Token</h2>
        <div class="kv">
          <div class="k">SKU</div>
          <div class="v"><code v-if="tokenSku">{{ tokenSku }}</code><span v-else>-</span></div>
          <div v-if="tokenExpiry" class="k">过期时间</div>
          <div v-if="tokenExpiry" class="v">
            {{ formatDate(tokenExpiry.expDate) }}
            <span class="tag" :class="tokenExpiry.remainMin > 5 ? 'green' : 'red'" style="margin-left: 6px;">
              {{ tokenExpiry.remainMin }} 分钟
            </span>
          </div>
          <div class="k">能力</div>
          <div class="v">
            <span v-for="cap in tokenCaps" :key="cap" class="tag blue" style="margin: 2px 4px 2px 0;">{{ cap }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Endpoint URLs -->
    <div v-if="apiKey" class="card">
      <h2><span class="dot"></span>常用 URL</h2>
      <div style="display: flex; flex-direction: column; gap: 8px;">
        <div class="copy-row">
          <span style="color: var(--text-dim); min-width: 130px;">Base URL</span>
          <span class="text">{{ baseUrl }}/v1</span>
          <button class="copy-btn" :class="{ copied: copiedKey === 'base' }" @click="copy(`${baseUrl}/v1`, 'base')">
            {{ copiedKey === 'base' ? '✓' : '📋' }}
          </button>
        </div>
        <div class="copy-row">
          <span style="color: var(--text-dim); min-width: 130px;">Chat Completions</span>
          <span class="text">{{ baseUrl }}/v1/chat/completions</span>
          <button class="copy-btn" :class="{ copied: copiedKey === 'chat' }" @click="copy(`${baseUrl}/v1/chat/completions`, 'chat')">
            {{ copiedKey === 'chat' ? '✓' : '📋' }}
          </button>
        </div>
        <div class="copy-row">
          <span style="color: var(--text-dim); min-width: 130px;">Models</span>
          <span class="text">{{ baseUrl }}/v1/models</span>
          <button class="copy-btn" :class="{ copied: copiedKey === 'models' }" @click="copy(`${baseUrl}/v1/models`, 'models')">
            {{ copiedKey === 'models' ? '✓' : '📋' }}
          </button>
        </div>
        <div class="copy-row">
          <span style="color: var(--text-dim); min-width: 130px;">Embeddings</span>
          <span class="text">{{ baseUrl }}/v1/embeddings</span>
          <button class="copy-btn" :class="{ copied: copiedKey === 'emb' }" @click="copy(`${baseUrl}/v1/embeddings`, 'emb')">
            {{ copiedKey === 'emb' ? '✓' : '📋' }}
          </button>
        </div>
        <div class="copy-row">
          <span style="color: var(--text-dim); min-width: 130px;">Anthropic Messages</span>
          <span class="text">{{ baseUrl }}/v1/messages</span>
          <button class="copy-btn" :class="{ copied: copiedKey === 'msg' }" @click="copy(`${baseUrl}/v1/messages`, 'msg')">
            {{ copiedKey === 'msg' ? '✓' : '📋' }}
          </button>
        </div>
        <div class="copy-row">
          <span style="color: var(--text-dim); min-width: 130px;">Usage</span>
          <span class="text">{{ baseUrl }}/usage</span>
          <button class="copy-btn" :class="{ copied: copiedKey === 'usage' }" @click="copy(`${baseUrl}/usage`, 'usage')">
            {{ copiedKey === 'usage' ? '✓' : '📋' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Models -->
    <div v-if="models.length" class="card">
      <h2><span class="dot"></span>可用模型 ({{ models.length }})</h2>
      <input class="search" v-model="search" placeholder="搜索模型 ID / 显示名 / 提供商..." />
      <div class="tabs">
        <button class="tab" :class="{ active: ownerFilter === 'all' }" @click="ownerFilter = 'all'">全部 ({{ models.length }})</button>
        <button v-for="o in ownerList" :key="o" class="tab"
          :class="{ active: ownerFilter === o }" @click="ownerFilter = o">
          {{ o }} ({{ models.filter(m => (m.owned_by || '-') === o).length }})
        </button>
      </div>
      <div class="scroll">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>显示名</th>
              <th>提供商</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in filteredModels" :key="m.id + (m.display_name || '')">
              <td>{{ m.id }}</td>
              <td>{{ m.display_name || '-' }}</td>
              <td>{{ m.owned_by || '-' }}</td>
              <td style="text-align: right;">
                <button class="copy-btn" :class="{ copied: copiedKey === 'model_' + m.id }" @click="copy(m.id, 'model_' + m.id)">
                  {{ copiedKey === 'model_' + m.id ? '✓' : '📋' }}
                </button>
              </td>
            </tr>
            <tr v-if="!filteredModels.length">
              <td colspan="4" style="text-align: center; color: var(--text-dim); padding: 20px;">无匹配结果</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Code snippets -->
    <div v-if="apiKey" class="card">
      <h2><span class="dot"></span>调用示例</h2>
      <div class="tabs">
        <button class="tab" :class="{ active: usageTab === 'curl' }" @click="usageTab = 'curl'">curl</button>
        <button class="tab" :class="{ active: usageTab === 'python' }" @click="usageTab = 'python'">Python</button>
        <button class="tab" :class="{ active: usageTab === 'node' }" @click="usageTab = 'node'">Node.js</button>
        <button class="tab" :class="{ active: usageTab === 'cherry' }" @click="usageTab = 'cherry'">客户端</button>
      </div>
      <div style="position: relative;">
        <button class="copy-btn" :class="{ copied: copiedKey === 'code_' + usageTab }"
          style="position: absolute; top: 8px; right: 8px; background: var(--panel-2); padding: 4px 10px; z-index: 1;"
          @click="copy(codeSnippets[usageTab], 'code_' + usageTab)">
          {{ copiedKey === 'code_' + usageTab ? '已复制 ✓' : '复制' }}
        </button>
        <pre class="code"><code>{{ codeSnippets[usageTab] }}</code></pre>
      </div>
    </div>

    <footer>
      <p>
        copilot-api dashboard ·
        <a href="https://github.com/ericc-ch/copilot-api" target="_blank">ericc-ch/copilot-api</a> ·
        Built with Vue 3 + Vite
      </p>
    </footer>

    <Transition>
      <div v-if="toast" class="toast" :class="toast.type">{{ toast.msg }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.v-enter-active, .v-leave-active { transition: opacity .2s; }
.v-enter-from, .v-leave-to { opacity: 0; }
</style>
