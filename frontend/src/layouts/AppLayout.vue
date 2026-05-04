<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">AM</div>
        <div class="brand-copy">
          <div class="brand-title">Another Me</div>
          <div class="brand-subtitle">写作分身</div>
        </div>
      </div>

      <nav class="nav">
        <el-tooltip content="风格库" placement="right" :disabled="!sidebarCollapsed">
          <RouterLink to="/styles" class="nav-item">
            <Collection />
            <span>风格库</span>
          </RouterLink>
        </el-tooltip>
        <el-tooltip content="写文章" placement="right" :disabled="!sidebarCollapsed">
          <RouterLink to="/write" class="nav-item">
            <EditPen />
            <span>写文章</span>
          </RouterLink>
        </el-tooltip>
      </nav>

      <el-tooltip :content="sidebarCollapsed ? '展开菜单' : '收起菜单'" placement="right">
        <button class="sidebar-toggle" type="button" :aria-label="sidebarCollapsed ? '展开菜单' : '收起菜单'" @click="toggleSidebar">
          <Expand v-if="sidebarCollapsed" />
          <Fold v-else />
        </button>
      </el-tooltip>
    </aside>

    <main class="workspace">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { Collection, EditPen, Expand, Fold } from '@element-plus/icons-vue'
import { onMounted, ref, watch } from 'vue'

const SIDEBAR_STORAGE_KEY = 'vibe-writer-sidebar-collapsed'
const sidebarCollapsed = ref(false)

onMounted(() => {
  sidebarCollapsed.value = localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true'
})

watch(sidebarCollapsed, (value) => {
  localStorage.setItem(SIDEBAR_STORAGE_KEY, String(value))
})

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}
</script>
