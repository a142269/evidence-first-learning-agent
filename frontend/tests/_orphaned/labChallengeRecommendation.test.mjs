// B · 闯关推荐规范化测试
// 测试 next-best-question、mistakes、generateMulti quiz 三种返回形态能规范成挑战题。
// 测试空数据回退到 CHALLENGE_BANK。

import assert from 'node:assert/strict'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const modulePath = join(__dirname, '../integrated-map-src/src/utils/challengeRecommendation.js')

const {
  normalizeChallenge,
  normalizeNextBestQuestion,
  normalizeMistakes,
  normalizeGenerateMultiQuiz,
  normalizeRecommendations,
  getRecommendedChallenges,
} = await import(`file://${modulePath}`)

// ── 1. normalizeChallenge: 基本规范化 ──
{
  const raw = {
    id: 'test-001',
    title: '测试题目',
    question: '这是一道测试题？',
    options: ['选项 A', '选项 B', '选项 C', '选项 D'],
    correctIndex: 2,
    explanation: '解析说明',
    difficulty: 3,
    kpId: 'kp-test-1',
    subject: 'ai',
    reward: { points: 25, exp: 50 },
    source: 'test',
    reason: '测试推荐理由',
  }
  const result = normalizeChallenge(raw, 'test', 0)
  assert.ok(result, 'normalizeChallenge should return a challenge object')
  assert.equal(result.id, 'test-001')
  assert.equal(result.title, '测试题目')
  assert.equal(result.question, '这是一道测试题？')
  assert.equal(result.options.length, 4)
  assert.equal(result.correctIndex, 2)
  assert.equal(result.difficulty, 3)
  assert.equal(result.kpId, 'kp-test-1')
  assert.equal(result.source, 'test')
  assert.equal(result.reason, '测试推荐理由')
  assert.equal(result.reward.points, 25)
}

// ── 2. normalizeChallenge: 字段名变体 ──
{
  const raw = {
    question_id: 'q-002',
    question_text: '变体字段题？',
    choices: ['A', 'B'],
    correct_index: 1,
    kp_id: 'kp-2',
    difficulty_level: 4,
  }
  const result = normalizeChallenge(raw, 'variant', 0)
  assert.ok(result, 'Should normalize variant field names')
  assert.equal(result.id, 'q-002')
  assert.equal(result.question, '变体字段题？')
  assert.equal(result.options.length, 2)
  assert.equal(result.correctIndex, 1)
  assert.equal(result.kpId, 'kp-2')
  assert.equal(result.difficulty, 4)
}

// ── 3. normalizeChallenge: 无效输入返回 null ──
{
  assert.equal(normalizeChallenge(null, 'test', 0), null, 'null input should return null')
  assert.equal(normalizeChallenge({}, 'test', 0), null, 'Empty object without question should return null')
  assert.equal(normalizeChallenge(undefined, 'test', 0), null, 'undefined input should return null')
}

// ── 4. normalizeNextBestQuestion: 正常返回 ──
{
  const response = {
    questions: [
      {
        question_id: 'nbq-001',
        kp_name: '感知机',
        kp_id: 'kp-perceptron',
        question: '感知机的学习算法优化什么？',
        options: ['最大化类间距离', '最小化误分类距离之和', '最大化似然', '最小化均方误差'],
        correct_index: 1,
        reason: 'BKT 不确定性最高',
        difficulty: 2,
      },
      {
        question_id: 'nbq-002',
        kp_name: '过拟合',
        kp_id: 'kp-overfitting',
        question: '哪种方法抑制过拟合？',
        options: ['增加层数', '减少数据', '正则化', '提高学习率'],
        correct_index: 2,
        difficulty: 2,
      },
    ],
  }
  const results = normalizeNextBestQuestion(response)
  assert.equal(results.length, 2, 'Should normalize 2 questions from next-best-question')
  assert.equal(results[0].id, 'nbq-001')
  assert.equal(results[0].question, '感知机的学习算法优化什么？')
  assert.equal(results[0].source, 'next-best-question')
  assert.equal(results[0].kpId, 'kp-perceptron')
  assert.equal(results[0].reason, 'BKT 不确定性最高')
  assert.equal(results[1].id, 'nbq-002')
}

// ── 5. normalizeNextBestQuestion: 空数据 ──
{
  assert.deepEqual(normalizeNextBestQuestion(null), [], 'null response should return empty array')
  assert.deepEqual(normalizeNextBestQuestion({}), [], 'Empty object should return empty array')
  assert.deepEqual(normalizeNextBestQuestion({ questions: [] }), [], 'Empty questions array should return empty array')
}

// ── 6. normalizeMistakes: 正常返回 ──
{
  const response = {
    mistakes: [
      {
        id: 'mistake-001',
        kp_name: '梯度下降',
        kp_id: 'kp-gd',
        question: '梯度下降的方向是什么？',
        student_answer: '梯度方向',
        correct_answer: '负梯度方向',
        error_type: 'concept_confusion',
        difficulty: 2,
      },
    ],
  }
  const results = normalizeMistakes(response)
  assert.equal(results.length, 1, 'Should normalize 1 mistake')
  assert.equal(results[0].id, 'mistake-001')
  assert.equal(results[0].source, 'mistakes')
  assert.equal(results[0].question, '梯度下降的方向是什么？')
  assert.equal(results[0].errorType, 'concept_confusion')
  // Options should be populated from student/correct answers since no options were provided
  assert.ok(results[0].options.length >= 2, 'Mistake without options should have fallback options')
  assert.ok(
    results[0].options.some((opt) => String(opt) === '负梯度方向'),
    'Fallback options should include the correct answer',
  )
}

// ── 7. normalizeGenerateMultiQuiz: 正常返回 ──
{
  const response = {
    results: [
      {
        type: 'quiz',
        data: {
          questions: [
            {
              id: 'gen-q-001',
              title: '生成题目 1',
              question: '什么是反向传播？',
              options: ['链式法则计算梯度', '前向传播', '随机搜索', '暴力枚举'],
              correct_index: 0,
              explanation: '反向传播使用链式法则',
              difficulty: 3,
              kp_id: 'kp-backprop',
            },
          ],
        },
      },
      {
        type: 'document',
        data: { content: 'some document' },
      },
    ],
  }
  const results = normalizeGenerateMultiQuiz(response)
  assert.equal(results.length, 1, 'Should extract 1 quiz question from generate/multi results')
  assert.equal(results[0].id, 'gen-q-001')
  assert.equal(results[0].source, 'generate-multi-quiz')
  assert.equal(results[0].question, '什么是反向传播？')
  assert.equal(results[0].correctIndex, 0)
}

// ── 8. normalizeGenerateMultiQuiz: 空数据 ──
{
  assert.deepEqual(normalizeGenerateMultiQuiz(null), [], 'null response should return empty array')
  assert.deepEqual(normalizeGenerateMultiQuiz({}), [], 'Empty object should return empty array')
  assert.deepEqual(normalizeGenerateMultiQuiz({ results: [] }), [], 'Empty results should return empty array')
  assert.deepEqual(
    normalizeGenerateMultiQuiz({ results: [{ type: 'document' }] }),
    [],
    'Non-quiz results should return empty array',
  )
}

// ── 9. getRecommendedChallenges: 空数据回退到 CHALLENGE_BANK ──
{
  // All API functions fail → should fall back to CHALLENGE_BANK
  const failingApi = {
    nextBestQuestion: async () => { throw new Error('unavailable') },
    getMistakesList: async () => { throw new Error('unavailable') },
    getRecommendations: async () => { throw new Error('unavailable') },
  }
  const challenges = await getRecommendedChallenges(
    { userId: 'test-user' },
    failingApi,
  )
  assert.ok(challenges.length > 0, 'Should fall back to CHALLENGE_BANK when all APIs fail')
  assert.equal(challenges[0].source, 'bank', 'Fallback challenges should have source "bank"')
  assert.ok(challenges[0].question, 'Bank challenges should have a question')
  assert.ok(challenges[0].options, 'Bank challenges should have options')
  assert.ok(typeof challenges[0].correctIndex === 'number', 'Bank challenges should have correctIndex')
}

// ── 10. getRecommendedChallenges: next-best-question 成功 ──
{
  const api = {
    nextBestQuestion: async () => ({
      questions: [
        {
          question_id: 'rec-001',
          question: '推荐题？',
          options: ['A', 'B', 'C', 'D'],
          correct_index: 1,
          kp_id: 'kp-1',
          difficulty: 2,
        },
      ],
    }),
    getMistakesList: async () => { throw new Error('unavailable') },
    getRecommendations: async () => { throw new Error('unavailable') },
  }
  const challenges = await getRecommendedChallenges(
    { userId: 'test-user' },
    api,
  )
  assert.ok(challenges.length >= 1, 'Should return at least 1 challenge from next-best-question')
  assert.equal(challenges[0].source, 'next-best-question')
  assert.equal(challenges[0].question, '推荐题？')
}

// ── 11. getRecommendedChallenges: mistakes 成功 ──
{
  const api = {
    nextBestQuestion: async () => { throw new Error('unavailable') },
    getMistakesList: async () => ({
      mistakes: [
        {
          id: 'm-001',
          kp_name: '错题知识点',
          question: '这道题你做错了？',
          student_answer: '错误答案',
          correct_answer: '正确答案',
          error_type: 'careless',
          difficulty: 1,
        },
      ],
    }),
    getRecommendations: async () => { throw new Error('unavailable') },
  }
  const challenges = await getRecommendedChallenges(
    { userId: 'test-user' },
    api,
  )
  assert.ok(challenges.length >= 1, 'Should return at least 1 challenge from mistakes')
  assert.equal(challenges[0].source, 'mistakes')
  assert.equal(challenges[0].question, '这道题你做错了？')
}

// ── 12. getRecommendedChallenges: topic 触发 generateMulti ──
{
  const api = {
    nextBestQuestion: async () => { throw new Error('unavailable') },
    getMistakesList: async () => { throw new Error('unavailable') },
    getRecommendations: async () => { throw new Error('unavailable') },
    generateMulti: async (params) => {
      assert.ok(params.types.includes('quiz'), 'generateMulti should be called with quiz type')
      assert.equal(params.topic, '线性回归', 'Topic should be passed through')
      return {
        results: [
          {
            type: 'quiz',
            data: {
              questions: [
                {
                  id: 'gen-001',
                  question: '线性回归的损失函数是？',
                  options: ['MSE', '交叉熵', 'KL 散度', 'Hinge'],
                  correct_index: 0,
                  difficulty: 2,
                },
              ],
            },
          },
        ],
      }
    },
  }
  const challenges = await getRecommendedChallenges(
    { userId: 'test-user', topic: '线性回归' },
    api,
  )
  assert.ok(challenges.length >= 1, 'Should return generated quiz challenges')
  assert.equal(challenges[0].source, 'generate-multi-quiz')
  assert.equal(challenges[0].question, '线性回归的损失函数是？')
}

// ── 13. normalizeNextBestQuestion: 真实后端返回（嵌套 question 对象 + 字母答案）──
{
  const response = {
    user_id: 'user-001',
    strategy: 'entropy',
    top_k: 5,
    based_on: 'bkt',
    recommendations: [
      {
        question: {
          id: 'q-python_basics-00',
          kp_id: 'python_basics',
          kp_name: 'Python 基础',
          bloom: 'Remember',
          type: 'multiple_choice',
          stem: '下列哪一项最准确描述不可变类型？',
          difficulty: 1,
          explanation: '不可变类型是该领域的基础概念。',
          options: [
            '不可变类型',
            'JVM 字节码',
            'GIL 是 Java 概念',
            'Python 强类型不需检查',
          ],
          answer: 'A',
        },
        score: 0.9999,
        p_correct: 0.5,
        reason: 'entropy_uncertainty',
        kp_id: 'python_basics',
        bloom: 'Remember',
      },
    ],
  }
  const results = normalizeNextBestQuestion(response)
  assert.equal(results.length, 1, 'Should normalize 1 recommendation from real backend format')
  assert.equal(results[0].id, 'q-python_basics-00')
  assert.equal(results[0].question, '下列哪一项最准确描述不可变类型？')
  assert.equal(results[0].options.length, 4)
  assert.equal(results[0].correctIndex, 0, 'Letter answer A should map to index 0')
  assert.equal(results[0].kpId, 'python_basics')
  assert.equal(results[0].source, 'next-best-question')
  assert.equal(results[0].reason, 'entropy_uncertainty')
}

// ── 14. normalizeGenerateMultiQuiz: 真实后端返回（results 是字典，quiz 题在 content 的 quiz_json 块） ──
{
  const quizQuestions = [
    {
      id: 'gen-quiz-001',
      stem: '什么是梯度下降？',
      options: ['沿负梯度方向迭代', '沿正梯度方向迭代', '随机方向', '不迭代'],
      answer: 'A',
      kp_id: 'gradient_descent',
      kp_name: '梯度下降',
      difficulty: 2,
      explanation: '梯度下降沿负梯度方向更新参数',
    },
    {
      id: 'gen-quiz-002',
      stem: '学习率过大会导致什么？',
      options: ['收敛太慢', '震荡或发散', '无影响', '梯度消失'],
      answer: 'B',
      kp_id: 'gradient_descent',
      kp_name: '梯度下降',
      difficulty: 2,
    },
  ]
  const response = {
    topic: '梯度下降',
    types_requested: ['quiz'],
    types_succeeded: ['quiz'],
    types_failed: [],
    results: {
      quiz: {
        success: true,
        type: 'quiz',
        content: '```quiz_json\n' + JSON.stringify(quizQuestions, null, 2) + '\n```',
        filepath: '/tmp/quiz.json',
        evidence: [],
        cov: {},
        safety: {},
        downloads: [],
        metadata: { topic: '梯度下降', quiz_count: 2 },
      },
    },
    success_count: 1,
  }
  const results = normalizeGenerateMultiQuiz(response)
  assert.equal(results.length, 2, 'Should extract 2 quiz questions from quiz_json code block in dict results')
  assert.equal(results[0].id, 'gen-quiz-001')
  assert.equal(results[0].question, '什么是梯度下降？')
  assert.equal(results[0].options.length, 4)
  assert.equal(results[0].correctIndex, 0, 'Letter A should map to index 0')
  assert.equal(results[0].source, 'generate-multi-quiz')
  assert.equal(results[1].correctIndex, 1, 'Letter B should map to index 1')
}

// ── 15. normalizeGenerateMultiQuiz: 真实后端返回，quiz 失败时返回空 ──
{
  const response = {
    results: {
      quiz: {
        success: false,
        type: 'quiz',
        content: '',
        error: 'Generation failed',
      },
    },
  }
  const results = normalizeGenerateMultiQuiz(response)
  assert.deepEqual(results, [], 'Failed quiz generation should return empty array')
}

// ── 16. normalizeGenerateMultiQuiz: 字典 results 但无 quiz 类型 ──
{
  const response = {
    results: {
      document: {
        success: true,
        type: 'document',
        content: 'Some document content',
      },
    },
  }
  const results = normalizeGenerateMultiQuiz(response)
  assert.deepEqual(results, [], 'Non-quiz dict results should return empty array')
}

console.log('labChallengeRecommendation: all normalization and fallback tests passed.')
