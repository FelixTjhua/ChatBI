import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

const md = new MarkdownIt({
  html: false,
  linkify: false,
  breaks: true,
  typographer: true,
  quotes: '“”‘’',
  highlight: (str: any, lang: any): string => {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs">
                  <div>${hljs.highlight(str, { language: lang, ignoreIllegals: true }).value}</div>
                </pre>`
      } catch {
        // 代码高亮失败，使用默认渲染
      }
    }

    return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>'
  },
})

export default md
