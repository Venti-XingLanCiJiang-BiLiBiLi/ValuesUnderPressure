<script setup lang="ts">
/**
 * NotFoundView — 404 页面
 */
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<template>
  <section class="mx-auto max-w-3xl px-6 py-20 text-center">
    <p class="text-6xl mb-4">·</p>
    <h1 class="font-serif text-3xl font-semibold text-ink-900 dark:text-ink-100 mb-2">
      页面不见了
    </h1>
    <p class="text-ink-500 dark:text-ink-400 mb-8">你访问的路径不存在</p>
    <button class="btn-primary" @click="router.push({ name: 'intro' })">回到开屏</button>
  </section>
</template>
