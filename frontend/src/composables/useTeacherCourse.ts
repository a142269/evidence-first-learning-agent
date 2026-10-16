/**
 * 教师端课程选择 · 全教师页面共享（模块级单例 + localStorage 持久化）。
 * 课程清单与显示名均来自真实接口 /api/v1/knowledge/courses（course.yaml 清单驱动），
 * 前端不再维护写死的 slug→中文名映射表（2026-07-16 知识库平台化改造）。
 */
import { computed, ref } from "vue";

import { listCourses, type CourseInfo } from "@/api/knowledge";

const STORAGE_KEY = "tripleu.teacher.course";
const DEFAULT_COURSE_ID = "artificial_intelligence";

function readStored(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

const course = ref(readStored() || DEFAULT_COURSE_ID);
const courseOptions = ref<string[]>([course.value]);
// 服务端下发的 slug → 显示名（course.yaml manifest）
const displayNames = ref<Record<string, string>>({});
let coursesLoaded = false;

export function courseLabelOf(courseId: string): string {
  return displayNames.value[courseId] || courseId.replace(/[-_]/g, " ");
}

export function useTeacherCourse() {
  const courseLabel = computed(() => courseLabelOf(course.value));

  /** 拉取真实课程清单（仅首次调用触发请求） */
  async function loadCourseOptions(force = false) {
    if (coursesLoaded && !force) return;
    coursesLoaded = true;
    try {
      const result = await listCourses();
      const ids: string[] = [];
      for (const item of result.courses || []) {
        if (typeof item === "string") {
          if (item) ids.push(item);
          continue;
        }
        const info = item as CourseInfo;
        const id = String(info.id || info.name || "");
        if (!id) continue;
        ids.push(id);
        if (info.display_name) displayNames.value[id] = String(info.display_name);
      }
      if (ids.length) {
        courseOptions.value = Array.from(new Set(ids));
        if (!courseOptions.value.includes(course.value)) {
          course.value = courseOptions.value[0];
        }
      }
    } catch {
      // 后端未连接时保留默认课程，不打断页面
    }
  }

  function setCourse(next: string) {
    if (!next || next === course.value) return;
    course.value = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* 隐私模式等场景忽略持久化失败 */
    }
  }

  return { course, courseLabel, courseOptions, loadCourseOptions, setCourse, courseLabelOf };
}
