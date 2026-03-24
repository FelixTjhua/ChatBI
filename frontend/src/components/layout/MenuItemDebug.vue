<template>
  <div class="debug-icons">
    <h3>图标调试</h3>
    <div class="icon-test">
      <span>Chat图标:</span>
      <ChatIcon style="width: 24px; height: 24px; color: #a855f7;" />
    </div>
    <div class="icon-test">
      <span>Dashboard图标:</span>
      <DashboardIcon style="width: 24px; height: 24px; color: #a855f7;" />
    </div>
    <div class="icon-test">
      <span>DS图标:</span>
      <DsIcon style="width: 24px; height: 24px; color: #a855f7;" />
    </div>
  </div>
</template>

<script setup lang="ts">
import ChatIcon from '@/assets/svg/menu/icon_chat_filled.svg'
import DashboardIcon from '@/assets/svg/menu/icon_dashboard_filled.svg'
import DsIcon from '@/assets/svg/menu/icon_database_filled.svg'
</script>

<style scoped>
.debug-icons {
  padding: 20px;
  background: #1a1033;
  color: white;
}
.icon-test {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 10px 0;
}
</style>
