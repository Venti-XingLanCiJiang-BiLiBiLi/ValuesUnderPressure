/**
 * 可复现的伪随机数生成器（mulberry32）。
 *
 * 移植自 backend/app/selection.py 对 random.Random(seed) 的使用方式：
 * 只需满足「同一 seed 在 TS 内部可复现」，不要求与 Python random 输出一致。
 *
 * 提供：
 *   - random()          → [0, 1) 浮点数
 *   - int(n)            → [0, n) 整数
 *   - shuffle(arr)      → 就地洗牌（Fisher-Yates）
 *   - sample(pop, k)    → 不放回随机取 k 个元素（Fisher-Yates 部分版）
 */

/** mulberry32：32 位种子 → [0, 1) 浮点数生成函数。 */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export class Rng {
  private next: () => number

  constructor(seed?: number | null) {
    // seed 缺省时按系统熵初始化（对应 Python random.Random() 的无参行为）
    if (seed === undefined || seed === null) {
      seed = Math.floor(Math.random() * 0xffffffff)
    }
    this.next = mulberry32(seed)
  }

  /** [0, 1) 均匀浮点数。 */
  random(): number {
    return this.next()
  }

  /** [0, n) 均匀整数。 */
  int(n: number): number {
    return Math.floor(this.next() * n)
  }

  /** 就地 Fisher-Yates 洗牌。 */
  shuffle<T>(arr: T[]): void {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = this.int(i + 1)
      const tmp = arr[i]!
      arr[i] = arr[j]!
      arr[j] = tmp
    }
  }

  /** 不放回随机取 k 个元素（对应 Python random.sample；k 超过长度时抛错）。 */
  sample<T>(population: T[], k: number): T[] {
    if (k < 0 || k > population.length) {
      throw new RangeError(
        `sample size ${k} exceeds population size ${population.length}`,
      )
    }
    const result = population.slice()
    for (let i = 0; i < k; i++) {
      const j = i + this.int(result.length - i)
      const tmp = result[i]!
      result[i] = result[j]!
      result[j] = tmp
    }
    return result.slice(0, k)
  }
}
