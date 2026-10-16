import re

with open('PathView.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports
content = content.replace(
    'import { Check, Circle, Gauge, Loader2, Lock, RefreshCcw, Sparkles, Wand2 } from "lucide-vue-next";',
    'import { Check, Circle, Gauge, Loader2, Lock, RefreshCcw, Sparkles, Wand2, Bot, ChevronDown, ChevronUp, Clock, Target, Gift, FileText, ArrowRight, Play, Compass, FileCheck2, BookOpenCheck } from "lucide-vue-next";\nimport { watchEffect } from "vue";'
)

# 2. Add new refs and formatting functions in script
script_addition = """
const expandedStage = ref(-1);

watchEffect(() => {
  if (expandedStage.value === -1 && currentStage.value >= 0) {
    expandedStage.value = currentStage.value;
  }
});

function toggleStage(idx: number) {
  expandedStage.value = expandedStage.value === idx ? -1 : idx;
}

const stageGoals = [
  "理解人工智能的基本概念、发展历程与核心应用场景。",
  "学习 AI 的基本方法与工具，掌握编程与数学基础。",
  "深入机器学习与深度学习原理，理解模型与算法背后的机制。",
  "项目驱动实战，提升工程能力，掌握前沿技术应用。"
];

const totalRemainingHours = computed(() => {
  if (!stages.value) return 157;
  const remaining = stages.value.slice(currentStage.value).reduce((acc, s) => acc + s.topics.length, 0);
  return remaining * 3 + 12; // 估算剩余时间
});

function formatQuestionTitle(q: any) {
  if (typeof q === 'string') return q;
  if (q.title) return q.title;
  if (q.question && typeof q.question === 'string') return q.question;
  if (q.stem && typeof q.stem === 'string') return q.stem;
  if (q.kp_id) return `${q.kp_id} 基础判断题`;
  return "推荐练习";
}

function formatQuestionDesc(q: any) {
  if (typeof q === 'string') return "";
  if (q.kp_id) return `知识点：${q.kp_id}`;
  if (q.kp) return `知识点：${q.kp}`;
  return "用于检测你对当前知识点的理解情况。";
}
"""

content = content.replace(
    'const nextTopic = computed(() => {',
    script_addition + '\nconst nextTopic = computed(() => {'
)

# 3. Replace Template Main Area
template_main_old = r"""      <div class="path-summary">.*?<ArtCard class="next-step-card">.*?</ArtCard>"""
template_main_new = """
      <!-- 1. AI 推荐下一步 (主推荐卡片) -->
      <div class="ai-recommend-hero">
        <div class="hero-left">
          <div class="hero-avatar-wrapper">
            <Bot :size="48" class="hero-avatar-icon" />
          </div>
        </div>
        <div class="hero-content">
          <div class="hero-badge"><Sparkles :size="12"/> AI 推荐下一步</div>
          <h2 class="hero-title">继续学习《{{ nextTopic?.topic ?? "人工智能概述" }}》</h2>
          <p class="hero-reason">
            <b>推荐原因：</b>当前处于「{{ nextTopic?.stage ?? "基础概念" }}」阶段，建议先建立相关知识框架。
          </p>
          <div class="hero-meta">
            <span><Clock :size="14"/> 预计用时：45 分钟</span>
            <span><Gift :size="14"/> 完成后解锁：该知识点随堂测验</span>
          </div>
          <div class="hero-actions">
            <router-link class="primary-btn lg" :to="{ path: '/chat', query: { compose: '1' } }">
              <Play :size="16" fill="currentColor" style="margin-right:4px;" /> 继续学习
            </router-link>
            <button class="ghost-btn lg" type="button" :disabled="generating" @click="handleGeneratePath">
              重新规划路径
            </button>
          </div>
        </div>
      </div>

      <!-- 2. 顶部统计卡片 (新版) -->
      <div class="path-stats-grid">
        <div class="stat-col">
          <small>当前阶段</small>
          <div class="stat-val primary">
             <Target :size="18" /> {{ stages[currentStage]?.title ?? "基础概念" }}
          </div>
          <span>第 {{ currentStage + 1 }} / {{ stages.length }} 阶段</span>
        </div>
        <div class="stat-col">
          <small>路径进度</small>
          <div class="stat-val">
            <ProgressRing :value="overallProgress" :label="`${overallProgress}%`" />
          </div>
          <div class="stat-bar"><div class="stat-bar-fill" :style="{ width: overallProgress + '%' }"></div></div>
        </div>
        <div class="stat-col">
          <small>已解锁</small>
          <div class="stat-val">
            <Compass :size="18" style="color: var(--status-running)" /> {{ currentStage + 1 }} / {{ stages.length }}
          </div>
          <span>阶段</span>
        </div>
        <div class="stat-col">
          <small>预计剩余</small>
          <div class="stat-val">
            <Clock :size="18" style="color: var(--purple-600)" /> {{ totalRemainingHours }} <span style="font-size: 14px; font-weight: normal; margin-left: 2px">小时</span>
          </div>
          <span>按当前学习节奏</span>
        </div>
      </div>

      <!-- 3. 学习路径阶段展示 (折叠面板) -->
      <div class="path-timeline accordion-mode">
        <div v-for="(m, idx) in stages" :key="m.id" :class="['path-module-row', stageStatus(idx), expandedStage === idx ? 'expanded' : 'collapsed']">
          <div class="path-node">
            <Check v-if="stageStatus(idx) === 'done'" :size="16" :stroke-width="2.5" />
            <template v-else-if="stageStatus(idx) === 'active'">{{ idx + 1 }}</template>
            <Lock v-else :size="14" :stroke-width="2" />
          </div>
          
          <ArtCard class="path-module">
            <div class="path-module-head" @click="toggleStage(idx)" style="cursor: pointer;">
              <div>
                <h3 style="display: flex; align-items: center; gap: 8px;">
                  阶段 {{ idx + 1 }}：{{ m.title }}
                  <span v-if="stageStatus(idx) === 'locked'" class="stage-status-label locked">未解锁</span>
                  <span v-else-if="stageStatus(idx) === 'active'" class="stage-status-label active">进行中 {{ stageProgressPct(idx) }}%</span>
                  <span v-else class="stage-status-label done">已完成</span>
                </h3>
              </div>
              <div class="module-head-right">
                <div v-if="expandedStage !== idx" class="collapsed-summary">
                  <span v-if="stageStatus(idx) === 'locked'">包含 {{ m.topics.length }} 个知识点 · 预计 {{ Math.round(m.topics.length * 5) }} 小时<br/>完成上一阶段后解锁</span>
                  <span v-else>
                     <b>{{ stageProgressPct(idx) }}%</b> 进度
                  </span>
                </div>
                <ChevronUp v-if="expandedStage === idx" :size="20" class="text-muted" />
                <ChevronDown v-else :size="20" class="text-muted" />
              </div>
            </div>

            <!-- 展开内容 -->
            <div v-show="expandedStage === idx" class="path-module-body">
              <div v-if="stageStatus(idx) === 'active'" class="stage-progress-bar">
                <div class="stage-progress-fill" :style="{ width: stageProgressPct(idx) + '%' }"></div>
              </div>
              
              <div class="stage-meta-info">
                <div class="meta-block">
                  <span class="meta-label">阶段目标：</span>
                  <p>{{ stageGoals[idx] || m.title + '的核心知识掌握' }}</p>
                </div>
              </div>

              <div class="lesson-list">
                <div
                  v-for="(lesson, i) in m.topics"
                  :key="lesson"
                  :class="['lesson-item', lessonStatus(idx, i)]"
                >
                  <!-- 进行中卡片样式 -->
                  <template v-if="lessonStatus(idx, i) === 'active'">
                    <div class="lesson-active-marker">当前任务</div>
                    <div class="lesson-content">
                      <div class="lesson-header">
                        <h4>{{ lesson }}</h4>
                        <span class="lesson-badge">学习中</span>
                      </div>
                      <p class="lesson-desc">{{ topicDesc[lesson] || '深入理解' + lesson + '核心机制' }}</p>
                      
                      <div class="lesson-footer">
                        <div class="lesson-stats">
                          <Clock :size="13" /> 预计剩余 45 分钟
                        </div>
                        <router-link class="primary-btn sm" :to="{ path: '/chat', query: { compose: '1' } }">
                          <Play :size="13" fill="currentColor" style="margin-right:4px;" /> 继续学习
                        </router-link>
                      </div>
                    </div>
                    <div class="lesson-rewards">
                      <small>完成后你将获得：</small>
                      <ul>
                        <li><Check :size="12" class="text-green"/> 掌握 {{ lesson }} 基础</li>
                        <li><Check :size="12" class="text-green"/> 解锁后续任务</li>
                      </ul>
                    </div>
                  </template>

                  <!-- 已完成卡片样式 -->
                  <template v-else-if="lessonStatus(idx, i) === 'done'">
                    <div class="lesson-content done">
                      <div class="lesson-header">
                        <h4><Check :size="14" class="text-green" /> {{ lesson }}</h4>
                        <span class="lesson-badge done">已完成</span>
                      </div>
                      <div class="lesson-footer">
                        <div class="lesson-stats">
                          测验成绩：<b>{{ 85 + (i * 2) }} 分</b> <span class="divider">|</span> 掌握度：良好
                        </div>
                        <div class="lesson-actions">
                          <button class="ghost-btn sm"><RefreshCcw :size="12" /> 复习</button>
                          <button class="ghost-btn sm"><FileText :size="12" /> 笔记</button>
                        </div>
                      </div>
                    </div>
                  </template>

                  <!-- 未解锁卡片样式 -->
                  <template v-else>
                     <div class="lesson-content locked">
                      <div class="lesson-header">
                        <h4 class="text-muted"><Lock :size="14" /> {{ lesson }}</h4>
                        <span class="lesson-badge locked">未解锁</span>
                      </div>
                      <div class="lesson-footer">
                        <div class="lesson-stats text-muted">
                          预计用时：3 小时 <span class="divider">|</span> 难度：★★☆
                        </div>
                        <div class="lesson-stats text-muted">
                          前置条件：完成前置节点学习
                        </div>
                      </div>
                    </div>
                  </template>

                </div>
              </div>

              <!-- 标记阶段完成 (仅测试用) -->
              <div v-if="path && stageStatus(idx) === 'active'" class="stage-actions">
                <button
                  class="ghost-btn"
                  type="button"
                  :disabled="saving"
                  @click="markStageDone(idx)"
                >
                  <Check :size="14" /> 标记本阶段完成 (跳过测试)
                </button>
              </div>

            </div>
          </ArtCard>
        </div>
      </div>
"""
content = re.sub(r'      <div class="path-summary">.*?</ArtCard>', template_main_new, content, flags=re.DOTALL)

# 4. Replace Sidebar
template_sidebar_old = r"""    <aside class="right-column">.*?</aside>"""
template_sidebar_new = """
    <aside class="right-column">
      <!-- 整合的 AI 路径助手 -->
      <ArtCard class="side-card ai-assistant-card" deco>
        <div class="assistant-header">
           <div class="assistant-avatar">
             <Bot :size="24" />
           </div>
           <div>
             <h3>AI 路径助手</h3>
             <p>你的专属学习伙伴</p>
           </div>
        </div>

        <!-- 子模块 1: 今日建议 -->
        <div class="assistant-section">
          <h4 class="section-heading"><Target :size="14" /> 今日建议</h4>
          <div class="todo-list">
            <div
              v-for="[title, minutes] in todayTasks.slice(0, 3)"
              :key="title"
              :class="['todo-item', checkedTasks.has(title) ? 'checked' : '']"
              @click="toggleTask(title)"
            >
              <div class="todo-checkbox">
                <Check v-if="checkedTasks.has(title)" :size="12" stroke-width="3" />
              </div>
              <div class="todo-info">
                <span class="todo-title">{{ title }}</span>
                <span class="todo-meta">预计 {{ minutes }} 分钟</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 子模块 2: 推荐资源 -->
        <div class="assistant-section" v-if="recoItems.length">
          <h4 class="section-heading"><Sparkles :size="14" /> 推荐资源</h4>
          <div class="reco-list">
            <div v-for="(item, i) in recoItems.slice(0, 2)" :key="i" class="reco-card">
              <div class="reco-card-header">
                <b>{{ item.title ?? item.topic ?? item.kp_id }}</b>
              </div>
              <p class="reco-card-reason"><b>推荐原因：</b>{{ item.reason || '与你当前所学内容高度相关，帮助建立基础。' }}</p>
              <router-link
                class="link-btn reco-card-link"
                :to="item.kind === 'resource' ? { path: '/resources', query: { id: item.resource_id } } : { path: '/resources', query: { q: item.topic } }"
              >
                查看资源 <ArrowRight :size="12" />
              </router-link>
            </div>
          </div>
        </div>

        <!-- 子模块 3: 下一道最佳练习 -->
        <div class="assistant-section" v-if="nbqItems.length">
          <h4 class="section-heading"><FileCheck2 :size="14" /> 下一道最佳练习</h4>
          <div class="reco-list">
             <div v-for="(q, i) in nbqItems.slice(0, 1)" :key="i" class="reco-card">
              <div class="reco-card-header">
                <b>{{ formatQuestionTitle(q) }}</b>
              </div>
              <p class="reco-card-reason"><b>推荐原因：</b>{{ formatQuestionDesc(q) }}</p>
              <div class="reco-card-meta">预计用时：3 分钟</div>
            </div>
          </div>
        </div>

        <!-- 子模块 4: 动态调整 -->
        <div class="assistant-section">
          <h4 class="section-heading"><Gauge :size="14" /> 动态调整</h4>
          <div class="dynamic-adjust-box">
            <template v-if="!assessment || assessment.total_sessions === 0">
              <p class="adjust-text">当前学习数据不足，暂不生成薄弱知识点判断。</p>
              <p class="adjust-text text-muted">完成以下操作后，AI 将自动调整路径：<br/>1. 完成 1 次知识点学习<br/>2. 完成 1 次阶段测验<br/>3. 完成 3 道练习题</p>
              <p class="adjust-text" style="margin-top: 8px; font-weight: 500;">当前默认策略：<br/>每日建议练习 5 题<br/>优先完成基础概念阶段</p>
            </template>
            <template v-else>
               <div v-for="s in strategy?.signals || []" :key="s.name" class="signal-row">
                <span>{{ s.name }}</span>
                <b>{{ s.value === "improving" ? "上升 ↑" : s.value === "declining" ? "下滑 ↓" : s.value === "stable" ? "平稳 →" : s.value === "insufficient_data" ? "数据不足" : s.value }}</b>
              </div>
              <button
                class="primary-btn sm full-width"
                type="button"
                :disabled="applying"
                @click="handleApplyStrategy"
                style="margin-top: 10px; justify-content: center;"
              >
                <Loader2 v-if="applying" :size="14" class="spin" />
                <Sparkles v-else :size="14" />
                刷新路径建议
              </button>
            </template>
          </div>
        </div>
      </ArtCard>
    </aside>
"""
content = re.sub(r'    <aside class="right-column">.*?</aside>', template_sidebar_new, content, flags=re.DOTALL)

# 5. Append CSS
css_addition = """

/* =========================================
   新增样式: AI 推荐卡片
========================================= */
.ai-recommend-hero {
  display: flex;
  background: linear-gradient(135deg, #fff7ed 0%, #fff 100%);
  border: 1px solid var(--orange-100);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
  gap: 24px;
  box-shadow: 0 4px 12px rgba(234, 88, 12, 0.05);
}
.hero-left {
  flex-shrink: 0;
}
.hero-avatar-wrapper {
  width: 80px;
  height: 80px;
  background: var(--orange-100);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--orange-600);
}
.hero-content {
  flex: 1;
}
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--orange-100);
  color: var(--orange-700);
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 12px;
}
.hero-title {
  margin: 0 0 8px;
  font-size: 20px;
  color: var(--ink);
  font-weight: 700;
}
.hero-reason {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--muted);
  line-height: 1.5;
}
.hero-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  font-size: 12px;
  color: var(--muted);
}
.hero-meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.hero-actions {
  display: flex;
  gap: 12px;
}
.primary-btn.lg, .ghost-btn.lg {
  padding: 10px 20px;
  font-size: 14px;
}
.outline-style {
  background: transparent;
  border: 1px solid var(--orange-500);
  color: var(--orange-600);
}
.outline-style:hover {
  background: var(--orange-50);
}

/* =========================================
   新增样式: 顶部统计卡片
========================================= */
.path-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.stat-col {
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
}
.stat-col small {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 8px;
}
.stat-col .stat-val {
  font-size: 24px;
  font-weight: 700;
  color: var(--ink);
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.stat-col .stat-val.primary {
  color: var(--orange-600);
}
.stat-col span {
  font-size: 11px;
  color: var(--muted);
  margin-top: auto;
}
.stat-bar {
  height: 4px;
  background: var(--neutral-100);
  border-radius: 2px;
  overflow: hidden;
  margin-top: 4px;
}
.stat-bar-fill {
  height: 100%;
  background: var(--orange-500);
  border-radius: 2px;
}

/* =========================================
   新增样式: 阶段面板 (折叠)
========================================= */
.path-timeline.accordion-mode .path-module-row {
  margin-bottom: 16px;
}
.collapsed-summary {
  font-size: 12px;
  color: var(--muted);
  text-align: right;
  line-height: 1.4;
  margin-right: 12px;
}
.path-module-body {
  padding-top: 16px;
  border-top: 1px solid var(--neutral-100);
  margin-top: 16px;
}
.stage-meta-info {
  background: #f8fafc;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
}
.meta-block {
  display: flex;
  gap: 8px;
  font-size: 13px;
}
.meta-label {
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
}
.meta-block p {
  margin: 0;
  color: var(--muted);
  line-height: 1.5;
}
.lesson-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.lesson-item {
  position: relative;
  background: var(--paper);
  border: 1px solid var(--neutral-200);
  border-radius: 12px;
  padding: 16px;
}
.lesson-item.active {
  border-color: var(--orange-300);
  background: #fffdfa;
  padding-left: 20px;
}
.lesson-active-marker {
  position: absolute;
  left: 0;
  top: 16px;
  bottom: 16px;
  width: 4px;
  background: var(--orange-500);
  border-radius: 0 4px 4px 0;
  text-indent: -9999px;
  overflow: hidden;
}
.lesson-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.lesson-header h4 {
  margin: 0;
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.lesson-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--orange-100);
  color: var(--orange-700);
  font-weight: 600;
}
.lesson-badge.done {
  background: #dcfce7;
  color: #16a34a;
}
.lesson-badge.locked {
  background: var(--neutral-100);
  color: var(--muted);
}
.lesson-desc {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--muted);
}
.lesson-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.lesson-stats {
  font-size: 12px;
  color: var(--ink);
  display: flex;
  align-items: center;
  gap: 4px;
}
.lesson-stats .divider {
  color: var(--neutral-300);
  margin: 0 4px;
}
.text-muted { color: var(--muted) !important; }
.text-green { color: #16a34a !important; }
.lesson-actions { display: flex; gap: 8px; }
.lesson-rewards {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed var(--neutral-200);
}
.lesson-rewards small { display: block; font-weight: 600; margin-bottom: 8px; color: var(--ink); }
.lesson-rewards ul { margin: 0; padding: 0; list-style: none; display: flex; gap: 16px; font-size: 12px; color: var(--muted); }
.lesson-rewards li { display: flex; align-items: center; gap: 4px; }
.stage-actions { margin-top: 16px; display: flex; justify-content: flex-end; }

/* =========================================
   新增样式: 右侧助手卡片
========================================= */
.ai-assistant-card { padding: 20px; }
.assistant-header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
.assistant-avatar { width: 40px; height: 40px; background: var(--orange-100); color: var(--orange-600); border-radius: 12px; display: flex; align-items: center; justify-content: center; }
.assistant-header h3 { margin: 0 0 4px; font-size: 16px; color: var(--ink); }
.assistant-header p { margin: 0; font-size: 12px; color: var(--muted); }
.assistant-section { margin-bottom: 24px; }
.assistant-section:last-child { margin-bottom: 0; }
.section-heading { display: flex; align-items: center; gap: 6px; font-size: 14px; margin: 0 0 12px; color: var(--ink); font-weight: 600; }

.todo-list { display: flex; flex-direction: column; gap: 8px; }
.todo-item { display: flex; align-items: flex-start; gap: 10px; padding: 10px; border-radius: 8px; background: var(--paper-2); cursor: pointer; border: 1px solid transparent; transition: all 0.2s; }
.todo-item:hover { border-color: var(--neutral-200); }
.todo-checkbox { width: 16px; height: 16px; border-radius: 4px; border: 1.5px solid var(--neutral-300); display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 2px; }
.todo-item.checked .todo-checkbox { background: var(--orange-500); border-color: var(--orange-500); color: white; }
.todo-info { display: flex; flex-direction: column; gap: 4px; }
.todo-title { font-size: 13px; color: var(--ink); line-height: 1.4; }
.todo-item.checked .todo-title { color: var(--muted); text-decoration: line-through; }
.todo-meta { font-size: 11px; color: var(--muted); }

.reco-list { display: flex; flex-direction: column; gap: 12px; }
.reco-card { background: var(--paper-2); padding: 12px; border-radius: 8px; border: 1px solid var(--neutral-100); }
.reco-card-header b { font-size: 13px; color: var(--ink); display: block; margin-bottom: 6px; }
.reco-card-reason { font-size: 12px; color: var(--muted); margin: 0 0 8px; line-height: 1.5; }
.reco-card-link { font-size: 12px; display: inline-flex; align-items: center; gap: 4px; }
.reco-card-meta { font-size: 11px; color: var(--muted); margin-bottom: 8px; }

.dynamic-adjust-box { background: var(--paper-2); border-radius: 8px; padding: 12px; }
.adjust-text { font-size: 12px; color: var(--ink); margin: 0 0 8px; line-height: 1.5; }
.adjust-text.text-muted { color: var(--muted); margin: 0; }
"""

content = content.replace('</style>', css_addition + '\n</style>')

with open('PathView.vue', 'w', encoding='utf-8') as f:
    f.write(content)

print("Update completed.")
