<script setup lang="ts">
/**
 * TestView — 逐题作答页
 * --------------------------------------------------------------------------
 * - 顶部进度条 + 退出按钮
 * - 中间题目卡 + Y/N 两个大按钮
 * - 切题时左右滑入/滑出过渡
 * - 答完自动跳 /result
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTestStore } from '@/stores/test'
import { useSessionRestore } from '@/composables/useSessionRestore'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'
import ProgressBar from '@/components/ProgressBar.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
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

// #22：当前题是否已答（用于按钮 aria-pressed 状态）
const answered = computed(() =>
  question.value ? store.answers[question.value.question_id] : undefined,
)

// #19：答题键盘快捷键（Y/N 作答，↑/Backspace 上一题，↓ 下一题）
// 内部已由 choose / goBack / goNext 处理 loading 状态
useKeyboardShortcuts({
  onYes: () => choose('Y'),
  onNo: () => choose('N'),
  onBack: () => store.goBack(),
  onNext: () => store.goNext(),
})

async function choose(answer: AnswerValue) {
  if (store.loading) return
  await store.submitAnswer(answer)
  if (store.finished || store.result) {
    router.push({ name: 'result' })
  }
}

const showQuitConfirm = ref(false)

function quit() {
  showQuitConfirm.value = true
}

function cancelQuit() {
  showQuitConfirm.value = false
}

function confirmQuit() {
  clear()
  store.reset()
  showQuitConfirm.value = false
  router.push({ name: 'intro' })
}
</script>

<template>
  <section role="main" aria-label="价值观压力测试" class="mx-auto max-w-3xl px-6 py-8 sm:py-12">
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
        :current="store.progressIndex"
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
        aria-live="polite"
        aria-atomic="true"
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

        <div role="group" aria-label="作答选项" class="grid sm:grid-cols-2 gap-3 sm:gap-4">
          <!-- 选中态：外圈暖色渐变边框（wrapper 包边，不影响未选中样式） -->
          <div
            class="rounded-xl transition-all duration-200"
            :class="
              answered === 'Y'
                ? 'p-[2.5px] bg-gradient-to-r from-amber-400 via-orange-400 to-ember-500 shadow-lg shadow-orange-500/30'
                : ''
            "
          >
            <button
              type="button"
              class="btn-y w-full min-h-[88px] text-lg flex-col gap-1"
              :disabled="store.loading"
              aria-label="选择是"
              :aria-pressed="answered === 'Y'"
              @click="choose('Y')"
            >
              <span class="text-2xl font-semibold">Y</span>
              <span class="text-xs opacity-80">
                {{ answered === 'Y' ? '是 · 已选择 ✓' : '是 · 我会这么做' }}
              </span>
            </button>
          </div>
          <div
            class="rounded-xl transition-all duration-200"
            :class="
              answered === 'N'
                ? 'p-[2.5px] bg-gradient-to-r from-amber-400 via-orange-400 to-ember-500 shadow-lg shadow-orange-500/30'
                : ''
            "
          >
            <button
              type="button"
              class="btn-n w-full min-h-[88px] text-lg flex-col gap-1"
              :disabled="store.loading"
              aria-label="选择否"
              :aria-pressed="answered === 'N'"
              @click="choose('N')"
            >
              <span class="text-2xl font-semibold">N</span>
              <span class="text-xs opacity-70">
                {{ answered === 'N' ? '否 · 已选择 ✓' : '否 · 我不会' }}
              </span>
            </button>
          </div>
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

        <!-- 导航：误触后回退查看/修改，回退状态下可前进回进度点 -->
        <nav aria-label="题目导航" class="mt-6 flex items-center justify-center gap-3">
          <button
            v-if="store.canGoBack"
            type="button"
            class="btn-ghost !px-4 !py-2 text-sm"
            :disabled="store.loading"
            aria-label="返回上一题"
            @click="store.goBack()"
          >
            ← 上一题
          </button>
          <button
            v-if="store.canGoNext"
            type="button"
            class="btn-ghost !px-4 !py-2 text-sm"
            :disabled="store.loading"
            aria-label="下一题"
            @click="store.goNext()"
          >
            下一题 →
          </button>
        </nav>

        <!-- #19：键盘快捷键视觉提示（语义由按钮 aria-label 提供，视觉提示对读屏隐藏） -->
        <div
          class="mt-4 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-ink-400 dark:text-ink-500"
          aria-hidden="true"
        >
          <span><kbd class="kbd">Y</kbd> 是</span>
          <span><kbd class="kbd">N</kbd> 否</span>
          <span><kbd class="kbd">←</kbd> 上一题</span>
          <span><kbd class="kbd">→</kbd> 下一题</span>
        </div>
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
    <ConfirmDialog
      v-model:show="showQuitConfirm"
      title="退出测试"
      message="当前进度会丢失，确定退出本次测试？"
      confirmText="退出"
      cancelText="取消"
      @confirm="confirmQuit"
    />
  </section>
</template>
