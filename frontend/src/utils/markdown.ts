/**
 * Markdown 渲染工具
 * 支持代码块、表格、图片等高级特性
 */

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function renderMarkdown(md: string): string {
  if (!md) return '<p class="md-empty">内容为空</p>';
  let html = md;

  // 1. 代码块 ```...``` - 优先处理，避免内部内容被转义
  const codeBlocks: string[] = [];
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_m, lang, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push(`<pre class="md-code-block"><code class="language-${lang || 'text'}">${escapeHtml(code.trim())}</code></pre>`);
    return `<!--CODE_BLOCK_${idx}-->`;
  });

  // 2. 行内代码 `code`
  const inlineCodes: string[] = [];
  html = html.replace(/`([^`\n]+)`/g, (_m, code) => {
    const idx = inlineCodes.length;
    inlineCodes.push(`<code class="md-inline-code">${escapeHtml(code)}</code>`);
    return `<!--INLINE_CODE_${idx}-->`;
  });

  // 3. 转义 HTML 特殊字符（代码块/行内代码已保护）
  html = escapeHtml(html);

  // 4. 标题（###### ~ #）
  html = html.replace(/^######\s+(.+)$/gm, '<h6>$1</h6>');
  html = html.replace(/^#####\s+(.+)$/gm, '<h5>$1</h5>');
  html = html.replace(/^####\s+(.+)$/gm, '<h4>$1</h4>');
  html = html.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^##\s+(.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^#\s+(.+)$/gm, '<h1>$1</h1>');

  // 5. 水平分割线
  html = html.replace(/^---+/gm, '<hr class="md-hr" />');

  // 6. 引用块
  html = html.replace(/^&gt;\s?(.+)$/gm, '<blockquote class="md-quote">$1</blockquote>');

  // 7. 无序列表
  html = html.replace(/^[-*+]\s+(.+)$/gm, '<li class="md-li">$1</li>');
  html = html.replace(/(<li class="md-li">[\s\S]*?<\/li>)(?:\n(?!<li))/g, (m) => `<ul class="md-ul">${m}</ul>`);
  html = html.replace(/(<\/li>)\n(<li)/g, '$1$2');

  // 8. 有序列表
  html = html.replace(/^\d+\.\s+(.+)$/gm, '<li class="md-oli">$1</li>');
  html = html.replace(/(<li class="md-oli">[\s\S]*?<\/li>)(?:\n(?!<li))/g, (m) => `<ol class="md-ol">${m}</ol>`);
  html = html.replace(/(<\/li>)\n(<li class="md-oli")/g, '$1$2');

  // 9. 粗体 **text**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // 10. 斜体 *text*
  html = html.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');

  // 11. 链接 [text](url)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // 12. 图片 ![alt](url)
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" class="md-img" />');

  // 13. 表格 | a | b |
  html = html.replace(/(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)/g, (table) => {
    const rows = table.trim().split('\n');
    let tableHtml = '<table class="md-table">';
    rows.forEach((row, i) => {
      if (i === 1) return; // 跳过分隔行
      const cells = row.split('|').filter(c => c.trim() !== '');
      const tag = i === 0 ? 'th' : 'td';
      tableHtml += '<tr>' + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>';
    });
    tableHtml += '</table>';
    return tableHtml;
  });

  // 14. 段落：将连续非标签行包裹为 <p>
  html = html.replace(/^(?!<[hupolbrqta])(.+)$/gm, (line) => {
    if (line.trim() === '' || line.trim().startsWith('<!--')) return line;
    return `<p class="md-p">${line}</p>`;
  });

  // 15. 清理多余空行
  html = html.replace(/\n{3,}/g, '\n\n');

  // 16. 恢复代码块
  html = html.replace(/<!--CODE_BLOCK_(\d+)-->/g, (_m, idx) => codeBlocks[parseInt(idx)]);
  html = html.replace(/<!--INLINE_CODE_(\d+)-->/g, (_m, idx) => inlineCodes[parseInt(idx)]);

  return html;
}
