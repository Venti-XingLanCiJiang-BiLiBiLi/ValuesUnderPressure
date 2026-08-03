<script setup lang="ts">
/**
 * TestView — 逐题作答页
 * --------------------------------------------------------------------------
 * - 顶部进度条 + 退出按钮
 * - 中间题目卡 + Y/N 两个大按钮
 * - 切题时左右滑入/滑出过渡
 * - 答完自动跳 /result
 */
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTestStore } from '@/stores/test'
import { useSessionRestore } from '@/composables/useSessionRestore'
import ProgressBar from '@/components/ProgressBar.vue'
import type { AnswerValue } from '@/types/api'

const router = useRouter()
const store = useTestStore()
const { clear } = useSessionRestore()

onMounted(async () => {
  // 没有 session 时，尝试恢复
  if (!store.sessionId) {
    router.replace({ name: 'intro' })
  }
})

const question = computed(() => store.currentQuestion)
const isLast = computed(() => store.currentIndex === store.total - 1)

async function choose(answer: AnswerValue) {
  if (store.loading) return
  await store.submitAnswer(answer)
  if (store.finished || store.result) {
    router.push({ name: 'result' })
  }
}

function quit() {
  if (confirm('当前进度会丢失，确定退出本次测试？')) {
    clear()
    store.reset()
    router.push({ name: 'intro' })
  }
}
</script>

<template>
  <section class="mx-auto max-w-3xl px-6 py-8 sm:py-12">
    <!-- ============================== 顶部进度 ============================== -->
    <div class="mb-8">
      <div class="flex items-center justify-between mb-3">
        <button
          type="button"
          class="text-sm text-ink-500 hover:text-ink-800 transition-colors
                 dark:text-ink-400 dark:hover:text-ink-100"
          @click="quit"
        >
          ← 退出
        </button>
        <span class="text-xs text-ink-500 dark:text-ink-400 font-mono">
          Q{{ String((question?.index ?? 0) + 1).padStart(2, '0') }} / {{ store.total }}
        </span>
      </div>
      <ProgressBar
        :current="store.currentIndex"
        :total="store.total"
        :show-label="false"
      />
    </div>

    <!-- ============================== 加载态 ============================== -->
    <div
      v-if="store.loading && !question"
      class="card p-12 text-center"
    >
      <div
        class="inline-block h-10 w-10 animate-spin rounded-full border-2 border-ink-200 border-t-ember-500 mb-4
               dark:border-ink-700"
      />
      <p class="text-ink-500 dark:text-ink-400">准备下一题…</p>
    </div>

    <!-- ============================== 题目卡 ============================== -->
    <Transition
      mode="out-in"
      enter-active-class="transition-all duration-300 ease-out"
      leave-active-class="transition-all duration-200 ease-in absolute w-full"
      enter-from-class="opacity-0 translate-x-4"
      leave-to-class="opacity-0 -translate-x-4"
    >
      <article
        v-if="question"
        :key="question.question_id"
        class="card p-8 sm:p-12 relative"
      >
        <div class="text-center mb-8">
          <p class="text-xs uppercase tracking-[0.25em] text-ink-400 dark:text-ink-500 mb-4">
            取舍
          </p>
          <h2
            class="font-serif text-2xl sm:text-3xl leading-relaxed text-ink-900 dark:text-ink-50 font-medium"
          >
            {{ question.content }}
          </h2>
        </div>

        <div class="grid sm:grid-cols-2 gap-3 sm:gap-4">
          <button
            type="button"
            class="btn-y min-h-[88px] text-lg flex-col gap-1"
            :disabled="store.loading"
            @click="choose('Y')"
          >
            <span class="text-2xl font-semibold">Y</span>
            <span class="text-xs opacity-80">是 · 我会这么做</span>
          </button>
          <button
            type="button"
            class="btn-n min-h-[88px] text-lg flex-col gap-1"
            :disabled="store.loading"
            @click="choose('N')"
          >
            <span class="text-2xl font-semibold">N</span>
            <span class="text-xs opacity-70">否 · 我不会</span>
          </button>
        </div>

        <p class="mt-6 text-center text-xs text-ink-400 dark:text-ink-500">
          没有对错。跟随你的第一反应即可。
        </p>

        <p
          v-if="isLast"
          class="mt-3 text-center text-xs text-ember-600 dark:text-ember-400 font-medium"
        >
          最后一题
        </p>
      </article>
    </Transition>

    <!-- ============================== 错误 ============================== -->
    <p
      v-if="store.error"
      class="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200 text-center
             dark:bg-red-950/40 dark:text-red-300 dark:ring-red-900/50"
    >
      {{ store.error }}
    </p>
  </section>
</template>
