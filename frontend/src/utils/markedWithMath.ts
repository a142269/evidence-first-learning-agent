/**
 * 带 KaTeX 数学公式渲染的 marked 工具
 *
 * 不依赖 marked 扩展系统（marked-katex-extension 的正则规则要求 $$ 独占行，
 * 与 LLM 输出的内联 $$...$$ 不兼容），改为在 marked 解析前预处理：
 * 1. 提取 $$...$$ (块级) 和 $...$ (行内) 公式
 * 2. 用 katex.renderToString() 渲染为 HTML
 * 3. 用占位符替换公式，运行 marked.parse()
 * 4. 将占位符替换回 KaTeX HTML
 */
import { marked } from "marked";
import katex from "katex";

/** 渲染单个 LaTeX 公式为 HTML 字符串 */
function renderMath(latex: string, displayMode: boolean): string {
  try {
    return katex.renderToString(latex, {
      displayMode,
      throwOnError: false,
      output: "html",
    });
  } catch {
    // 渲染失败时回退为 <code> 显示原始 LaTeX，至少不丢内容
    return `<code>${escapeHtml(latex)}</code>`;
  }
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * 预处理文本中的数学公式，返回 { text, mathMap }
 * - text 中公式被替换为占位符
 * - mathMap 记录占位符 → KaTeX HTML 的映射
 */
function extractMath(text: string): { text: string; mathMap: Map<string, string> } {
  const mathMap = new Map<string, string>();
  let counter = 0;

  // 1. 先提取块级公式 $$...$$（贪婪匹配同一对 $$ 之间的内容，可跨行）
  //    使用 [\s\S] 匹配任意字符（含换行），非贪婪 ? 确保最短匹配
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_m, latex: string) => {
    const key = `KATEX_BLOCK_${counter++}`;
    mathMap.set(key, renderMath(latex.trim(), true));
    return key;
  });

  // 2. 再提取行内公式 $...$（不跨行，且 $ 后不能直接跟 $ 或空白）
  //    负向先行断言排除 $$ 残留和货币符号场景
  text = text.replace(
    /(?<!\$)\$(?!\$)([^\n$]+?)\$(?!\d)/g,
    (_m, latex: string) => {
      // 跳过空公式和明显不是公式的（如 $5 价格）
      const trimmed = latex.trim();
      if (!trimmed || /^\d+(\.\d+)?$/.test(trimmed)) return _m;
      const key = `KATEX_INLINE_${counter++}`;
      mathMap.set(key, renderMath(trimmed, false));
      return key;
    },
  );

  return { text, mathMap };
}

/**
 * 将 marked 输出中的占位符替换回 KaTeX HTML
 * 块级公式用 <div> 包裹（居中显示），行内公式直接插入
 */
function restoreMath(html: string, mathMap: Map<string, string>): string {
  for (const [key, mathHtml] of mathMap) {
    if (key.startsWith("KATEX_BLOCK_")) {
      // 块级公式：marked 可能将占位符包在 <p> 中，替换为独立的 div
      html = html.replace(
        new RegExp(`<p>\\s*${key}\\s*</p>`, "g"),
        `<div class="katex-block">${mathHtml}</div>`,
      );
      // 兜底：如果不在 <p> 中，直接替换
      html = html.replace(key, mathHtml);
    } else {
      html = html.replace(key, mathHtml);
    }
  }
  return html;
}

/**
 * 带 KaTeX 渲染的 marked.parse 包装
 * 用法与 marked.parse() 完全一致
 */
function parseWithMath(src: string): string {
  const { text, mathMap } = extractMath(src);
  const html = marked.parse(text) as string;
  return restoreMath(html, mathMap);
}

/** 导出带数学渲染的 marked 对象 */
export const markedWithMath = {
  parse: parseWithMath,
};

export { marked };
